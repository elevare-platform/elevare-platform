"""Celery tasks for the AI module — CV parsing pipeline, scoring, and embeddings."""

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.core.model_registry  # noqa: F401 — ensures all mappers are registered before any DB use
from app.core.celery_app import celery
from app.core.config import settings
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.repository import AIRepository
from app.modules.ai.scoring_service import (
    hash_cv_scoring_inputs,
    hash_job_scoring_inputs,
)
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.applications.repository import ApplicationRepository
from app.modules.candidates.repository import CandidateRepository
from app.modules.jobs.repository import JobRepository
from app.modules.talent_pool.repository import TalentPoolRepository

logger = logging.getLogger(__name__)


def _json_serialise(obj):
    """Custom JSON serialiser for types not handled by stdlib json."""
    from datetime import date, datetime

    if isinstance(obj, datetime | date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_full_pipeline_task(
    self,
    submission_id: str,
    cache_key: str,
    file: bytes | None = None,
    r2_key: str | None = None,
):
    """Celery task — synchronous wrapper around the async pipeline.

    Accepts either raw file bytes (legacy/manual upload path) or a pre-uploaded
    R2 key (ingestion path — avoids passing large bytes through Redis).
    Exactly one of file or r2_key must be provided.
    """
    asyncio.run(_run_pipeline_async(submission_id, cache_key, file=file, r2_key=r2_key))


async def _run_pipeline_async(
    submission_id_str: str,
    cache_key: str,
    file: bytes | None = None,
    r2_key: str | None = None,
) -> None:
    import dataclasses

    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.core.cv_pipeline.pipeline import run_extraction_pipeline
    from app.modules.ai.cv_parsing_repo import CVParsingRepo
    from app.modules.ai.models import CVParsingCost
    from app.modules.ai.service import AnthropicCVExtractionService

    submission_id = uuid.UUID(submission_id_str)

    # Create a fresh engine and session for this event loop — avoids
    # "Future attached to a different loop" from reusing the module-level engine
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with SessionLocal() as db:
        from app.core.storage import get_storage_service

        repo = CVParsingRepo(db, get_storage_service())

        import spacy

        nlp = spacy.load("en_core_web_sm")

        ai_service = AnthropicCVExtractionService()
        redis = aioredis.from_url(settings.redis_url)

        try:
            from datetime import UTC as _UTC
            from datetime import datetime as _datetime

            timestamp = _datetime.now(_UTC).strftime("%Y%m%d%H%M%S")
            submission_obj = await repo.get_by_id(submission_id)
            if not submission_obj:
                logger.error(
                    "Pipeline task: submission %s not found — may not be committed yet",
                    submission_id,
                )
                raise ValueError(f"Submission {submission_id} not found in DB")

            storage = get_storage_service()

            if r2_key:
                # File was pre-uploaded by the ingestion pipeline — download it
                # so the extraction pipeline can process it without Redis holding bytes
                file = await storage.download_file(r2_key)
                # Ensure the submission row has the r2_key recorded
                if not submission_obj.r2_key:
                    await repo.update(submission_id, {"r2_key": r2_key})
            else:
                # Manual upload path — upload bytes to R2 now
                uploader = submission_obj.uploaded_by or "system"
                r2_key = f"cv-parsing/{uploader}/{timestamp}_{submission_obj.filename}"
                await storage.upload_file(file, r2_key, "application/pdf")
                await repo.update(submission_id, {"r2_key": r2_key})

            await repo.update(
                submission_id, {"parse_status": CVParsingStatus.PROCESSING.value}
            )
            cv_result, (deterministic, llm_result, lang_result) = (
                await run_extraction_pipeline(file, nlp, ai_service)
            )

            flag_reasons = []
            if not lang_result.is_english:
                flag_reasons.append("CV is not written in English")
            if cv_result.is_scanned:
                flag_reasons.append("Scanned PDF — OCR used")
            if cv_result.overall_confidence < 0.6:
                flag_reasons.append("Low confidence extraction")

            parse_status = (
                CVParsingStatus.FLAGGED.value
                if flag_reasons
                else CVParsingStatus.COMPLETED.value
            )

            parsed_data = json.loads(
                json.dumps(dataclasses.asdict(cv_result), default=_json_serialise)
            )
            deterministic_data = json.loads(
                json.dumps(dataclasses.asdict(deterministic), default=_json_serialise)
            )
            llm_data = json.loads(
                json.dumps(dataclasses.asdict(llm_result), default=_json_serialise)
            )

            await repo.update(
                submission_id,
                {
                    "parse_status": parse_status,
                    "parsed_data": parsed_data,
                    "deterministic_data": deterministic_data,
                    "llm_data": llm_data,
                    "flag_reasons": flag_reasons or None,
                },
            )

            await redis.setex(
                cache_key, CACHE_TTL_SECONDS, json.dumps(parsed_data, default=str)
            )

            if llm_result.field_confidence.get("skills") not in (None, "low"):
                cost_row = CVParsingCost(
                    submission_id=submission_id,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=0.0,
                    model=settings.anthropic_model,
                )
                db.add(cost_row)

            await db.commit()

            # --- Trigger talent pool scoring for any profile linked to this submission
            # Handles the race where scoring was queued before parsing completed
            try:
                from sqlalchemy import select as _select

                from app.modules.talent_pool.models import TalentPoolProfiles

                tp_result = await db.execute(
                    _select(TalentPoolProfiles).where(
                        TalentPoolProfiles.parsed_submission_id == submission_id
                    )
                )
                for tp in list(tp_result.scalars().all()):
                    if tp.sourced_for_job_id:
                        score_talent_pool_profile_task.delay(
                            str(tp.id), str(tp.sourced_for_job_id)
                        )
                        logger.info(
                            "Pipeline complete — queued talent pool scoring for profile %s",
                            tp.id,
                        )
                    # Always queue embedding generation regardless of job context
                    from app.modules.ai.tasks import (
                        generate_talent_pool_embedding_task as _gen_tp_emb,
                    )

                    _gen_tp_emb.delay(str(tp.id))
            except Exception:
                logger.warning(
                    "Failed to trigger talent pool scoring after pipeline",
                    exc_info=True,
                )

        except Exception as e:
            logger.error(
                f"Pipeline task failed for submission {submission_id}", exc_info=True
            )
            try:
                await repo.update(
                    submission_id,
                    {
                        "parse_status": CVParsingStatus.FAILED.value,
                        "error_message": str(e),
                    },
                )
                await db.commit()
            except Exception:
                pass
            raise
        finally:
            await redis.aclose()
            await engine.dispose()
            # aclose() is the correct async close method for AsyncAnthropic
            try:
                await ai_service._client.close()
            except Exception:
                pass


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def score_application_task(self, application_id: str) -> None:
    """Compute ai_score, strengths, weaknesses, and fit_summary for an application.

    Exits early (no LLM call, no write) if both content hashes match the stored values.
    Re-fires automatically when job description/skills changes via the job update endpoint.
    """
    asyncio.run(_score_application_async(application_id))


async def _score_application_async(application_id_str: str) -> None:

    application_id = uuid.UUID(application_id_str)

    # Create a fresh engine and session for this event loop — avoids
    # "Future attached to a different loop" from reusing the module-level engine
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionLocal() as db:
        try:
            app_repo = ApplicationRepository(db)
            ai_repo = AIRepository(db)
            candidate_repo = CandidateRepository(db)
            job_repo = JobRepository(db)

            application = await app_repo.get_by_id(application_id)
            if not application:
                logger.warning(
                    f"score_application: Application {application_id} not found."
                )
                return

            # --- Load parsed CV data via the chain: Application -> CandidateCVs -> ParsedCVSubmission
            if not application.cv_id:
                logger.info(
                    "score_application: No CV for application {application_id}. Skipping."
                )
                return

            cv = await candidate_repo.get_cv(application.cv_id)
            if not cv:
                logger.warning(
                    "score_application: No CV found for application {application_id}"
                )
                return

            submission = await ai_repo.get_submission_by_id(cv.submission_id)
            if not submission or not submission.parsed_data:
                logger.info(
                    "score_application: No parsed submission for application {application_id}. Skipping."
                )
                return

            job = await job_repo.get_by_id(application.job_id)
            if not job:
                logger.warning(
                    f"score_application: Job not found for application {application_id}. Skipping."
                )
                return

            # --- Hash-based cache check - skip LLM if nothing changed
            from app.modules.jobs.schemas import build_full_description

            effective_description = build_full_description(
                about_the_role=job.about_the_role,
                key_responsibilities=job.key_responsibilities,
                requirements=job.requirements,
                preferred_certifications=job.preferred_certifications,
                technical_competencies=job.technical_competencies,
                what_we_offer=job.what_we_offer,
                legacy_description=job.description,
            )
            job_hash = hash_job_scoring_inputs(
                effective_description, job.required_skills or [], job.seniority_level
            )
            cv_hash = hash_cv_scoring_inputs(submission.parsed_data)

            # --- Skip LLM if nothing changed
            if (
                application.ai_score_job_hash == job_hash
                and application.ai_score_cv_hash == cv_hash
                and application.ai_score is not None
            ):
                logger.info(
                    f"score_application: Cache hit for application {application_id}. Skipping LLM."
                )
                return

            # --- LLM Layer ---
            parsed = submission.parsed_data
            ai_service = AnthropicCVExtractionService()

            try:
                # Build rich candidate context from work history
                work_history_lines = []
                for role in parsed.get("work_history") or []:
                    t = role.get("title") or ""
                    c = role.get("company") or ""
                    d = role.get("description") or ""
                    if t or d:
                        work_history_lines.append(
                            f"- {t}{' at ' + c if c else ''}: {d}".strip()
                        )
                work_history_text = "\n".join(work_history_lines) or "Not provided"

                candidate_context = (
                    f"Current title: {parsed.get('current_title') or 'Unknown'}\n"
                    f"Profession: {parsed.get('profession') or 'Unknown'}\n"
                    f"Years experience: {parsed.get('years_experience') or 'Unknown'}\n"
                    f"Work history:\n{work_history_text}\n"
                    f"Skills: {', '.join(parsed.get('skills') or [])}\n"
                    f"Summary: {parsed.get('summary') or ''}"
                )

                job_context = (
                    f"About the role: {job.about_the_role or job.description or ''}\n"
                    f"Key responsibilities: {job.key_responsibilities or ''}\n"
                    f"Requirements: {job.requirements or ''}\n"
                    f"Technical competencies: {job.technical_competencies or ''}\n"
                    f"Preferred certifications: {job.preferred_certifications or ''}"
                )

                reasoning = await ai_service.generate_fit_reasoning(
                    candidate_context=candidate_context,
                    job_context=job_context,
                )
            finally:
                # Close before the session/engine tears down so the loop is still alive
                await ai_service._client.close()

            await app_repo.update(
                application_id,
                {
                    "ai_score": reasoning.score,
                    "ai_strengths": reasoning.strengths,
                    "ai_weaknesses": reasoning.weaknesses,
                    "ai_fit_summary": reasoning.fit_summary,
                    "ai_score_job_hash": job_hash,
                    "ai_score_cv_hash": cv_hash,
                    "ai_score_computed_at": datetime.now(UTC),
                },
            )
            await db.commit()
            logger.info(
                f"score_application: scored application {application_id} -> {reasoning.score}"
            )
        except Exception:
            logger.exception(
                "score_application: failed for application %s", application_id
            )
            raise
        finally:
            await engine.dispose()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def score_talent_pool_profile_task(
    self, profile_id: str, job_id: str | None = None
) -> None:
    """Compute ai_score, strengths, weaknesses, and fit_summary for a Talent Pool profile.

    job_id is optional — if not provided, falls back to profile.sourced_for_job_id.
    Pass job_id explicitly when scoring retroactively from score_against_job.
    """
    asyncio.run(_score_talent_pool_profile_async(profile_id, job_id))


async def _score_talent_pool_profile_async(
    profile_id_str: str, job_id_str: str | None = None
) -> None:

    profile_id = uuid.UUID(profile_id_str)

    # Create a fresh engine and session for this event loop — avoids
    # "Future attached to a different loop" from reusing the module-level engine
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionLocal() as db:
        try:
            talent_pool_repo = TalentPoolRepository(db)
            ai_repo = AIRepository(db)
            job_repo = JobRepository(db)

            talent_pool = await talent_pool_repo.get_by_id(profile_id)
            if not talent_pool:
                logger.warning(
                    f"score_talent_pool_profile: Talent pool profile {profile_id} not found."
                )
                return

            # --- Load parsed CV data via the chain: TalentPool -> ParsedCVSubmission
            if not talent_pool.parsed_submission_id:
                logger.info(
                    "score_talent_pool_profile: No parsed submission for talent pool profile {profile_id}. Skipping."
                )
                return

            submission = await ai_repo.get_submission_by_id(
                talent_pool.parsed_submission_id
            )
            if not submission:
                logger.warning(
                    "score_talent_pool_profile: submission not found for profile %s",
                    profile_id,
                )
                return

            if not submission.parsed_data:
                # Parsing hasn't completed yet — reschedule after a delay
                # The pipeline task will also trigger scoring once it completes
                from app.modules.ai.enums import CVParsingStatus

                if submission.parse_status in (
                    CVParsingStatus.PENDING.value,
                    CVParsingStatus.PROCESSING.value,
                ):
                    logger.info(
                        "score_talent_pool_profile: parsing still in progress for profile %s, retrying in 30s",
                        profile_id,
                    )
                    raise Exception(
                        f"Parsing not complete for submission {submission.id} — will retry"
                    )
                else:
                    logger.warning(
                        "score_talent_pool_profile: submission %s has status %s with no parsed_data, skipping",
                        submission.id,
                        submission.parse_status,
                    )
                    return

            # Use explicitly passed job_id first, fall back to profile's sourced_for_job_id
            effective_job_id = (
                uuid.UUID(job_id_str) if job_id_str else talent_pool.sourced_for_job_id
            )
            if not effective_job_id:
                logger.info(
                    "score_talent_pool_profile: No job context for profile %s. Skipping.",
                    profile_id,
                )
                return

            job = await job_repo.get_by_id(effective_job_id)
            if not job:
                logger.warning(
                    f"score_talent_pool_profile: Job not found for talent pool profile {profile_id}. Skipping."
                )
                return

            # --- Hash-based cache check - skip LLM if nothing changed
            from app.modules.jobs.schemas import build_full_description

            effective_description = build_full_description(
                about_the_role=job.about_the_role,
                key_responsibilities=job.key_responsibilities,
                requirements=job.requirements,
                preferred_certifications=job.preferred_certifications,
                technical_competencies=job.technical_competencies,
                what_we_offer=job.what_we_offer,
                legacy_description=job.description,
            )
            job_hash = hash_job_scoring_inputs(
                effective_description, job.required_skills or [], job.seniority_level
            )
            cv_hash = hash_cv_scoring_inputs(submission.parsed_data)

            # --- Skip LLM if nothing changed
            if (
                talent_pool.ai_score_job_hash == job_hash
                and talent_pool.ai_score_cv_hash == cv_hash
                and talent_pool.ai_score is not None
            ):
                logger.info(
                    f"score_talent_profile_pool: Cache hit for talent_profile_pool {profile_id}. Skipping LLM."
                )
                return

            # --- LLM Layer ---
            parsed = submission.parsed_data
            ai_service = AnthropicCVExtractionService()

            try:
                # Build rich candidate context from work history
                tp_work_history_lines = []
                for role in parsed.get("work_history") or []:
                    t = role.get("title") or ""
                    c = role.get("company") or ""
                    d = role.get("description") or ""
                    if t or d:
                        tp_work_history_lines.append(
                            f"- {t}{' at ' + c if c else ''}: {d}".strip()
                        )
                tp_work_history_text = (
                    "\n".join(tp_work_history_lines) or "Not provided"
                )

                candidate_context = (
                    f"Current title: {parsed.get('current_title') or 'Unknown'}\n"
                    f"Profession: {parsed.get('profession') or 'Unknown'}\n"
                    f"Years experience: {parsed.get('years_experience') or 'Unknown'}\n"
                    f"Work history:\n{tp_work_history_text}\n"
                    f"Skills: {', '.join(parsed.get('skills') or [])}\n"
                    f"Summary: {parsed.get('summary') or ''}"
                )

                job_context = (
                    f"About the role: {job.about_the_role or job.description or ''}\n"
                    f"Key responsibilities: {job.key_responsibilities or ''}\n"
                    f"Requirements: {job.requirements or ''}\n"
                    f"Technical competencies: {job.technical_competencies or ''}\n"
                    f"Preferred certifications: {job.preferred_certifications or ''}"
                )

                reasoning = await ai_service.generate_fit_reasoning(
                    candidate_context=candidate_context,
                    job_context=job_context,
                )
            finally:
                # Close before the session/engine tears down so the loop is still alive
                await ai_service._client.close()

            await talent_pool_repo.update(
                profile_id,
                {
                    "ai_score": reasoning.score,
                    "ai_strengths": reasoning.strengths,
                    "ai_weaknesses": reasoning.weaknesses,
                    "ai_fit_summary": reasoning.fit_summary,
                    "ai_score_job_hash": job_hash,
                    "ai_score_cv_hash": cv_hash,
                    "ai_score_computed_at": datetime.now(UTC),
                },
            )
            await db.commit()
            logger.info(
                f"score_talent_pool_profile: scored talent_pool_profile {profile_id} -> {reasoning.score}"
            )
        except Exception:
            logger.exception(
                "score_talent_pool_profile: failed for talent_pool_profile %s",
                profile_id,
            )
            raise
        finally:
            await engine.dispose()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_candidate_embedding_task(self, profile_id: str) -> None:
    """Generate and store a profile embedding for a candidate.

    Skips if the embedding source hash hasn't changed since last generation.
    """
    asyncio.run(_generate_candidate_embedding_async(profile_id))


async def _generate_candidate_embedding_async(profile_id_str: str) -> None:
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from app.modules.ai.scoring_service import hash_candidate_embedding_source
    from app.modules.ai.service import EmbeddingAIService

    profile_id = uuid.UUID(profile_id_str)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        try:
            candidate_repo = CandidateRepository(db)
            ai_repo = AIRepository(db)

            profile = await candidate_repo.get_by_id(profile_id)
            if not profile:
                logger.warning(
                    "generate_candidate_embedding: profile %s not found", profile_id
                )
                return

            parsed_cv_summary: str | None = None
            parsed_current_title: str | None = None
            parsed_profession: str | None = None
            parsed_skills: list[str] | None = None
            work_history_parts: list[str] = []

            # Resolve parsed CV summary via the default CV → submission chain
            default_cv = next((cv for cv in profile.cvs if cv.is_default), None)
            if default_cv and default_cv.submission_id:
                submission = await ai_repo.get_submission_by_id(
                    default_cv.submission_id
                )
                if submission and submission.parsed_data:
                    pd = submission.parsed_data
                    parsed_cv_summary = pd.get("summary")
                    parsed_current_title = pd.get("current_title")
                    parsed_profession = pd.get("profession")
                    parsed_skills = pd.get("skills")

                    for role in pd.get("work_history") or []:
                        title = role.get("title") or ""
                        description = role.get("description") or ""

                        if description and title:
                            work_history_parts.append(
                                f"{title}: {description}".strip(": ")
                            )

            work_history_text = "\n".join(work_history_parts)
            # Candidate's own curated skills list takes priority over the
            # auto-extracted CV skills, same precedence used for display
            # elsewhere (talent_pool/service.py: resolve_match_display_fields).
            candidate_skills = profile.skills or parsed_skills or []

            # Hash check — skip if source content hasn't changed
            new_hash = hash_candidate_embedding_source(
                current_title=parsed_current_title,
                profession=parsed_profession,
                work_history_text=work_history_text,
                parsed_cv_summary=parsed_cv_summary,
                skills=candidate_skills,
            )

            if (
                profile.embedding_source_hash == new_hash
                and profile.profile_embedding is not None
            ):
                logger.info(
                    "generate_candidate_embedding: hash unchanged for profile %s, skipping",
                    profile_id,
                )
                return

            # Build embedding text - work history and role identity are primary
            # signals. Skills are included so unrelated professions with
            # similar-sounding narrative text (title/summary) don't land at
            # deceptively high similarity — skills are the clearest
            # discriminator between e.g. "HR" and "Machine Learning Engineer".
            skills_text = ", ".join(candidate_skills)
            embedding_text = (
                f"Current title: {parsed_current_title or ''}\n"
                f"Profession: {parsed_profession or ''}\n"
                f"Skills: {skills_text}\n"
                f"Work history:\n{work_history_text}\n"
                f"Summary: {parsed_cv_summary or ''}"
            ).strip()

            ai_service = EmbeddingAIService()
            embedding = await ai_service.generate_embedding(embedding_text)

            # Persist
            profile.profile_embedding = embedding
            profile.embedding_source_hash = new_hash
            profile.embedding_generated_at = _datetime.now(_UTC)

            # Propagate to the linked talent_pool_profiles row (if any) — that's
            # the table AI Talent Match actually queries. Self-registered
            # candidates never get an embedding generated on their own
            # talent-pool row otherwise (generate_talent_pool_embedding_task
            # only handles sourced-only rows with a parsed_submission_id), so
            # without this they could never appear in AI Talent Match at all.
            try:
                from sqlalchemy import select as _select

                from app.modules.talent_pool.models import TalentPoolProfiles

                tp_result = await db.execute(
                    _select(TalentPoolProfiles).where(
                        TalentPoolProfiles.candidate_profile_id == profile.id
                    )
                )
                tp_profile = tp_result.scalar_one_or_none()
                if tp_profile:
                    tp_profile.profile_embedding = embedding
                    tp_profile.embedding_source_hash = new_hash
                    tp_profile.embedding_generated_at = _datetime.now(_UTC)
            except Exception:
                logger.warning(
                    "generate_candidate_embedding: failed to propagate embedding "
                    "to talent_pool_profiles for candidate %s",
                    profile_id,
                    exc_info=True,
                )
            await db.commit()

            logger.info(
                "generate_candidate_embedding: stored embedding for profile %s",
                profile_id,
            )

            # Re-queue scoring for all pending applications — keyword fallback may have run first
            try:
                from sqlalchemy import select as _select

                from app.modules.applications.models import Application

                apps_result = await db.execute(
                    _select(Application).where(
                        Application.candidate_id == profile.user_id
                    )
                )
                for app in apps_result.scalars().all():
                    from app.modules.ai.tasks import (
                        score_application_task as _score_app,
                    )

                    _score_app.delay(str(app.id))
                logger.info(
                    "generate_candidate_embedding: re-queued scoring for %d applications",
                    len(apps_result.all() or []),
                )
            except Exception:
                logger.warning(
                    "generate_candidate_embedding: failed to re-queue application scoring",
                    exc_info=True,
                )

        except Exception:
            logger.exception(
                "generate_candidate_embedding: failed for profile %s", profile_id
            )
            raise
        finally:
            await engine.dispose()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_job_embedding_task(self, job_id: str) -> None:
    """Generate and store a job embedding.

    Skips if the embedding source hash hasn't changed since last generation.
    """
    asyncio.run(_generate_job_embedding_async(job_id))


async def _generate_job_embedding_async(job_id_str: str) -> None:
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from app.modules.ai.scoring_service import hash_job_embedding_source
    from app.modules.ai.service import EmbeddingAIService

    job_id = uuid.UUID(job_id_str)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        try:
            job_repo = JobRepository(db)

            job = await job_repo.get_by_id(job_id)
            if not job:
                logger.warning("generate_job_embedding: job %s not found", job_id)
                return

            # Hash check — skip if source content hasn't changed
            from app.modules.jobs.schemas import build_full_description

            effective_description = build_full_description(
                about_the_role=job.about_the_role,
                key_responsibilities=job.key_responsibilities,
                requirements=job.requirements,
                preferred_certifications=job.preferred_certifications,
                technical_competencies=job.technical_competencies,
                what_we_offer=job.what_we_offer,
                legacy_description=job.description,
            )
            new_hash = hash_job_embedding_source(
                description=effective_description,
                required_skills=job.required_skills,
                title=job.title,
            )
            if job.embedding_source_hash == new_hash and job.job_embedding is not None:
                logger.info(
                    "generate_job_embedding: hash unchanged for job %s, skipping",
                    job_id,
                )
                return

            # Build embedding text and generate vector — title and required_skills
            # are the strongest role-identity signals and must anchor the vector,
            # otherwise unrelated professions can land at non-trivial similarity.
            skills_text = ", ".join(job.required_skills or [])
            embedding_text = (
                f"Job title: {job.title}\n"
                f"Required skills: {skills_text}\n"
                f"Job description: {effective_description}"
            )

            ai_service = EmbeddingAIService()
            embedding = await ai_service.generate_embedding(embedding_text)

            # Persist
            job.job_embedding = embedding
            job.embedding_source_hash = new_hash
            job.embedding_generated_at = _datetime.now(_UTC)
            await db.commit()

            logger.info("generate_job_embedding: stored embedding for job %s", job_id)

        except Exception:
            logger.exception("generate_job_embedding: failed for job %s", job_id)
            raise
        finally:
            await engine.dispose()


@celery.task
def recompute_stale_scores_task() -> None:
    """Nightly Celery beat task — re-queues scoring for applications where the
    candidate's profile was updated after ai_score was last computed.

    Runs off-peak (configured in celery beat schedule).
    Only touches applications that are genuinely stale — bounded and cheap.
    """
    asyncio.run(_recompute_stale_scores_async())


async def _recompute_stale_scores_async() -> None:
    from sqlalchemy import select as _select

    from app.modules.applications.models import Application
    from app.modules.candidates.models import CandidateProfile

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        try:
            # Find applications where the candidate's profile was updated
            # after the ai_score was last computed — these scores are stale.
            stmt = (
                _select(Application.id)
                .join(
                    CandidateProfile,
                    CandidateProfile.user_id == Application.candidate_id,
                )
                .where(
                    Application.ai_score.is_not(None),
                    Application.ai_score_computed_at.is_not(None),
                    CandidateProfile.updated_at > Application.ai_score_computed_at,
                )
            )
            result = await db.execute(stmt)
            stale_ids = result.scalars().all()

            for app_id in stale_ids:
                score_application_task.delay(str(app_id))

            logger.info(
                "recompute_stale_scores: re-queued %d stale application(s)",
                len(stale_ids),
            )

        except Exception:
            logger.exception("recompute_stale_scores: failed")
            raise
        finally:
            await engine.dispose()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_talent_pool_embedding_task(self, profile_id: str) -> None:
    """Generate and store a profile embedding for a talent pool profile.

    Skips if the embedding source hash hasn't changed since last generation.
    """
    asyncio.run(_generate_talent_pool_embedding_async(profile_id))


async def _generate_talent_pool_embedding_async(profile_id_str: str) -> None:
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    from app.modules.ai.enums import CVParsingStatus
    from app.modules.ai.scoring_service import hash_talent_pool_embedding_source
    from app.modules.ai.service import EmbeddingAIService

    profile_id = uuid.UUID(profile_id_str)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        try:
            talent_pool_repo = TalentPoolRepository(db)
            ai_repo = AIRepository(db)

            profile = await talent_pool_repo.get_by_id(profile_id)
            if not profile:
                logger.warning(
                    "generate_talent_pool_embedding: profile %s not found", profile_id
                )
                return

            if not profile.parsed_submission_id:
                logger.info(
                    "generate_talent_pool_embedding: no submission for profile %s, skipping",
                    profile_id,
                )
                return

            submission = await ai_repo.get_submission_by_id(
                profile.parsed_submission_id
            )
            if not submission or not submission.parsed_data:
                logger.info(
                    "generate_talent_pool_embedding: no parsed data for profile %s, skipping",
                    profile_id,
                )
                return

            if submission.parse_status != CVParsingStatus.COMPLETED.value:
                # FLAGGED (low confidence / non-English / scanned-OCR) or
                # FAILED — don't spend an embedding call on a document that
                # may not even be a real CV. find_matches_for_job also
                # excludes these at query time; this just stops generating
                # them in the first place.
                logger.info(
                    "generate_talent_pool_embedding: parse_status=%s for profile %s, skipping",
                    submission.parse_status,
                    profile_id,
                )
                return

            parsed = submission.parsed_data
            summary = parsed.get("summary") or ""
            current_title = parsed.get("current_title") or ""
            profession = parsed.get("profession") or ""
            tp_work_history_parts: list[str] = []

            for role in parsed.get("work_history") or []:
                title = role.get("title") or ""
                description = role.get("description") or ""
                if title or description:
                    tp_work_history_parts.append(f"{title}: {description}".strip(": "))

            tp_work_history_text = "\n".join(tp_work_history_parts)
            tp_skills = parsed.get("skills") or []

            new_hash = hash_talent_pool_embedding_source(
                current_title=current_title,
                profession=profession,
                work_history_text=tp_work_history_text,
                summary=summary,
                skills=tp_skills,
            )

            if (
                profile.embedding_source_hash == new_hash
                and profile.profile_embedding is not None
            ):
                logger.info(
                    "generate_talent_pool_embedding: hash unchanged for profile %s, skipping",
                    profile_id,
                )
                return

            embedding_text = (
                f"Current title: {current_title}\n"
                f"Profession: {profession}\n"
                f"Skills: {', '.join(tp_skills)}\n"
                f"Work history:\n{tp_work_history_text}\n"
                f"Summary: {summary}"
            )

            ai_service = EmbeddingAIService()
            embedding = await ai_service.generate_embedding(embedding_text)

            profile.profile_embedding = embedding
            profile.embedding_source_hash = new_hash
            profile.embedding_generated_at = _datetime.now(_UTC)
            await db.commit()

            logger.info(
                "generate_talent_pool_embedding: stored embedding for profile %s",
                profile_id,
            )

            # Re-queue scoring now that embedding exists — keyword fallback may have run first
            if profile.sourced_for_job_id:
                from app.modules.ai.tasks import (
                    score_talent_pool_profile_task as _score_tp,
                )

                _score_tp.delay(str(profile_id), str(profile.sourced_for_job_id))
                logger.info(
                    "generate_talent_pool_embedding: re-queued scoring for profile %s",
                    profile_id,
                )

        except Exception:
            logger.exception(
                "generate_talent_pool_embedding: failed for profile %s", profile_id
            )
            raise
        finally:
            await engine.dispose()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def upload_cv_to_r2_task(
    self, submission_id: str, uploaded_by_id: str, filename: str, file: bytes
) -> None:
    """Upload a CV file to R2 and set the r2_key on the submission row.

    Used for cache-hit submissions where parsing is skipped but the file
    still needs to be stored so the download endpoint works.
    """
    asyncio.run(_upload_cv_to_r2_async(submission_id, uploaded_by_id, filename, file))


async def _upload_cv_to_r2_async(
    submission_id_str: str,
    uploaded_by_id_str: str,
    filename: str,
    file: bytes,
) -> None:
    from datetime import UTC as _UTC
    from datetime import datetime as _datetime

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        try:
            from app.core.storage import get_storage_service
            from app.modules.ai.cv_parsing_repo import CVParsingRepo

            repo = CVParsingRepo(db, get_storage_service())
            storage = get_storage_service()

            timestamp = _datetime.now(_UTC).strftime("%Y%m%d%H%M%S")
            r2_key = f"cv-parsing/{uploaded_by_id_str}/{timestamp}_{filename}"

            await storage.upload_file(file, r2_key, "application/pdf")
            await repo.update(uuid.UUID(submission_id_str), {"r2_key": r2_key})
            await db.commit()

            logger.info(
                "upload_cv_to_r2: stored %s for submission %s",
                r2_key,
                submission_id_str,
            )

        except Exception:
            logger.exception(
                "upload_cv_to_r2: failed for submission %s", submission_id_str
            )
            raise
        finally:
            await engine.dispose()
