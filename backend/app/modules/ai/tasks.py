import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import selectinload

import app.core.model_registry  # noqa: F401 — ensures all mappers are registered before any DB use
from app.core.celery_app import celery
from app.core.config import settings
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.scoring_service import (
    compute_deterministic_score,
    hash_cv_scoring_inputs,
    hash_job_scoring_inputs,
)
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.ai.repository import AIRepository
from app.modules.applications.repository import ApplicationRepository
from app.modules.candidates.repository import CandidateRepository
from app.modules.jobs.repository import JobRepository

logger = logging.getLogger(__name__)

def _json_serialise(obj):
    """Custom JSON serialiser for types not handled by stdlib json."""
    from datetime import datetime, date
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")

CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_full_pipeline_task(
    self,
    submission_id: str,  # UUID as string — Celery serialises to JSON
    cache_key: str,
    file: bytes,
):
    """Celery task — synchronous wrapper around the async pipeline."""
    asyncio.run(_run_pipeline_async(submission_id, cache_key, file))


async def _run_pipeline_async(
    submission_id_str: str,
    cache_key: str,
    file: bytes,
) -> None:
    import dataclasses
    import json

    import redis.asyncio as aioredis
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
            await repo.update(submission_id, {"parse_status": CVParsingStatus.PROCESSING.value})
            cv_result, (deterministic, llm_result, lang_result) = await run_extraction_pipeline(
                file, nlp, ai_service
            )

            flag_reasons = []
            if not lang_result.is_english:
                flag_reasons.append("CV is not written in English")
            if cv_result.is_scanned:
                flag_reasons.append("Scanned PDF — OCR used")
            if cv_result.overall_confidence < 0.6:
                flag_reasons.append("Low confidence extraction")

            parse_status = CVParsingStatus.FLAGGED.value if flag_reasons else CVParsingStatus.COMPLETED.value

            parsed_data = json.loads(json.dumps(dataclasses.asdict(cv_result), default=_json_serialise))
            deterministic_data = json.loads(json.dumps(dataclasses.asdict(deterministic), default=_json_serialise))
            llm_data = json.loads(json.dumps(dataclasses.asdict(llm_result), default=_json_serialise))

            await repo.update(submission_id, {
                "parse_status": parse_status,
                "parsed_data": parsed_data,
                "deterministic_data": deterministic_data,
                "llm_data": llm_data,
                "flag_reasons": flag_reasons or None,
            })

            await redis.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(parsed_data, default=str))

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

        except Exception as e:
            logger.error(f"Pipeline task failed for submission {submission_id}", exc_info=True)
            try:
                await repo.update(submission_id, {
                    "parse_status": CVParsingStatus.FAILED.value,
                    "error_message": str(e),
                })
                await db.commit()
            except Exception:
                pass
            raise
        finally:
            await redis.aclose()
            await engine.dispose()
            # Close the Anthropic httpx client before the event loop shuts down
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
    asyncio.run(
        _score_application_async(application_id)
    )

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
            job_hash = hash_job_scoring_inputs(
                job.description or "",
                job.required_skills or [],
                job.seniority_level
            )
            cv_hash = hash_cv_scoring_inputs(
                submission.parsed_data
            )

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
            
            # --- Deterministic score (no LLM)
            parsed = submission.parsed_data
            det_score = compute_deterministic_score(
                candidate_skills=parsed.get("skills") or [],
                candidate_years_experience=parsed.get("years_experience"),
                candidate_seniority=parsed.get("seniority_level"),
                job_required_skills=job.required_skills or [],
                job_seniority_level=job.seniority_level,
                job_min_years_experience=job.required_years_experience,
                job_max_years_experience=None,
            )

            # --- LLM Layer ---
            ai_service = AnthropicCVExtractionService()

            try:
                candidate_summary = (
                    f"Skills: {', '.join(parsed.get('skills') or [])}\n"
                    f"Years experience: {parsed.get('years_experience')}\n"
                    f"Seniority: {parsed.get('seniority_level')}\n"
                    f"Summary: {parsed.get('summary') or ''}"
                )

                reasoning = await ai_service.generate_fit_reasoning(
                    candidate_summary=candidate_summary,
                    job_description=job.description or "",
                    deterministic_score=det_score
                )
            finally:
                    try:
                        await ai_service._client.close()
                    except Exception:
                        pass
            
            await app_repo.update(application_id, {
                "ai_score": det_score,
                "ai_strengths": reasoning.strengths,
                "ai_weaknesses": reasoning.weaknesses,
                "ai_fit_summary": reasoning.fit_summary,
                "ai_score_job_hash": job_hash,
                "ai_score_cv_hash": cv_hash,
                "ai_score_computed_at": datetime.now(UTC),
            })
            await db.commit()
            logger.info(f"score_application: scored application {application_id} -> {det_score}")
        except Exception:
            logger.exception("score_application: failed for application %s", application_id)
            raise
        finally:
            await engine.dispose()

