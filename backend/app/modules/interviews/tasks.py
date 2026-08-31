"""Celery tasks for AI video interviews — email notifications, transcription, and scoring."""

import asyncio
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.core.model_registry  # noqa: F401 — ensures all mappers are registered before any DB use
from app.core.ai_pricing import (
    compute_anthropic_cost_usd,
    compute_transcription_cost_usd,
)
from app.core.celery_app import celery
from app.core.config import settings
from app.core.email import get_email_service
from app.core.exceptions import PlanUpgradeRequiredException
from app.core.storage import get_storage_service
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.billing.service import BillingService
from app.modules.interviews.enums import (
    STALE_INTERVIEW_TIMEOUT,
    InterviewCostComponent,
    InterviewStatus,
)
from app.modules.interviews.repository import InterviewRepository
from app.modules.notifications.repository import NotificationRepository
from app.modules.talent_pool.service import resolve_match_display_fields

logger = logging.getLogger(__name__)

# Whisper rejects files over 25MB. Recordings are video+audio, so raw bytes
# blow past that well before 20 minutes. Extracting just the audio track as
# low-bitrate mono mp3 (via ffmpeg) keeps a 20+ minute interview well under
# the cap: 64kbps mono ≈ 0.48MB/min, i.e. ~18.8MB for 40 minutes.
_WHISPER_AUDIO_BITRATE = "64k"
_WHISPER_AUDIO_SAMPLE_RATE = "16000"


async def _extract_audio_for_whisper(video_bytes: bytes) -> bytes:
    """Extract a low-bitrate mono audio track from a video recording via ffmpeg.

    Whisper only needs the audio, and a compressed audio-only file is a
    fraction of the size of the source video+audio recording — this is what
    keeps long interviews under Whisper's 25MB upload cap.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "input.webm"
        out_path = Path(tmpdir) / "output.mp3"
        in_path.write_bytes(video_bytes)

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(in_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            _WHISPER_AUDIO_SAMPLE_RATE,
            "-b:a",
            _WHISPER_AUDIO_BITRATE,
            str(out_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg audio extraction failed (exit {proc.returncode}): "
                f"{stderr.decode(errors='replace')[-2000:]}"
            )

        return out_path.read_bytes()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_ai_interview_invite_email(
    self,
    candidate_email: str,
    interview_url: str,
    job_title: str,
    company_name: str,
) -> None:
    """Send an AI interview invite email with a no-login magic link.

    Always the real token link, for every candidate — self-registered
    candidates aren't guaranteed to have an Application for this specific
    job (they may have been sourced via Candidate Search / Talent
    Matches), so a login-gated dashboard link would be a dead end
    whenever that's the case. The token link works for anyone.
    """

    async def _send():
        service = get_email_service()
        await service.send_ai_interview_invite(
            candidate_email=candidate_email,
            interview_url=interview_url,
            job_title=job_title,
            company_name=company_name,
        )

    try:
        asyncio.run(_send())
        logger.info(
            "AI interview invite email sent to %s for role '%s'",
            candidate_email,
            job_title,
        )
    except Exception as exc:
        logger.error(
            "Failed to send AI interview invite email to %s: %s",
            candidate_email,
            exc,
        )
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_interview_restart_request_email(
    self,
    employer_email: str,
    candidate_name: str,
    job_title: str,
    company_name: str,
    manage_url: str,
) -> None:
    """Notify an employer that a candidate is locked out of their AI
    interview's restart lock and needs it reset via a resend."""

    async def _send():
        service = get_email_service()
        await service.send_interview_restart_request(
            employer_email=employer_email,
            candidate_name=candidate_name,
            job_title=job_title,
            company_name=company_name,
            manage_url=manage_url,
        )

    try:
        asyncio.run(_send())
        logger.info(
            "Interview restart request email sent to %s for candidate '%s' on role '%s'",
            employer_email,
            candidate_name,
            job_title,
        )
    except Exception as exc:
        logger.error(
            "Failed to send interview restart request email to %s: %s",
            employer_email,
            exc,
        )
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def transcribe_and_score_interview_task(self, interview_id: str) -> None:
    """Transcribe an uploaded interview recording and score it against the job's brief.

    Transcription always runs and always saves, regardless of plan tier.
    Scoring (the LLM call) is gated to Professional+ orgs, mirroring how
    AI Talent Match CV scoring is gated — Starter interviews still end up
    SCORED with a transcript, just with no ai_score.
    """
    logger.info(
        "transcribe_and_score_interview_task: received interview_id=%s (celery task_id=%s, "
        "attempt=%d/%d)",
        interview_id,
        self.request.id,
        self.request.retries + 1,
        self.max_retries + 1,
    )
    is_final_attempt = self.request.retries >= self.max_retries
    asyncio.run(
        _transcribe_and_score_interview_async(
            interview_id, mark_failed_on_error=is_final_attempt
        )
    )


async def _transcribe_and_score_interview_async(
    interview_id_str: str, mark_failed_on_error: bool = True
) -> None:
    interview_id = uuid.UUID(interview_id_str)
    logger.info(
        "transcribe_and_score_interview: starting async pipeline for interview %s",
        interview_id,
    )

    # Fresh engine and session for this event loop — avoids "Future attached
    # to a different loop" from reusing a module-level engine across tasks.
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionLocal() as db:
        try:
            repo = InterviewRepository(db)

            interview = await repo.get_by_id(interview_id)
            if not interview:
                logger.warning(
                    "transcribe_and_score_interview: Interview %s not found — skipping",
                    interview_id,
                )
                return

            if interview.status != InterviewStatus.UPLOADED.value:
                logger.info(
                    "transcribe_and_score_interview: Interview %s is not UPLOADED "
                    "(status=%s) — skipping to avoid double-processing",
                    interview_id,
                    interview.status,
                )
                return

            if interview.transcript:
                # Already captured client-side from Realtime API transcript
                # events during the live session (diarized, both speakers)
                # — skip the R2 download + Whisper call entirely.
                transcript = interview.transcript
                logger.info(
                    "transcribe_and_score_interview: interview %s already has a "
                    "Realtime-captured transcript (%d chars) — skipping download/Whisper",
                    interview_id,
                    len(transcript),
                )
            else:
                logger.info(
                    "transcribe_and_score_interview: no transcript captured for "
                    "interview %s — falling back to downloading recording "
                    "(r2_key=%s)",
                    interview_id,
                    interview.r2_key,
                )
                video_bytes = await get_storage_service().download_file(interview.r2_key)
                logger.info(
                    "transcribe_and_score_interview: downloaded %d bytes for interview %s — "
                    "extracting audio via ffmpeg before transcribing via %s",
                    len(video_bytes),
                    interview_id,
                    settings.transcription_model,
                )

                audio_bytes = await _extract_audio_for_whisper(video_bytes)
                logger.info(
                    "transcribe_and_score_interview: extracted %d bytes of audio "
                    "(from %d bytes of video) for interview %s",
                    len(audio_bytes),
                    len(video_bytes),
                    interview_id,
                )

                openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
                try:
                    # verbose_json is what makes `.duration` available —
                    # whisper-1's default response format doesn't return
                    # usage/duration data, and per-minute Whisper pricing
                    # needs the audio duration regardless of model.
                    transcript_resp = await openai_client.audio.transcriptions.create(
                        file=("recording.mp3", audio_bytes),
                        model=settings.transcription_model,
                        response_format="verbose_json",
                    )
                finally:
                    await openai_client.close()

                transcript = transcript_resp.text
                logger.info(
                    "transcribe_and_score_interview: transcription complete for interview %s "
                    "(%d chars, %.1fs audio) — saving transcript",
                    interview_id,
                    len(transcript),
                    transcript_resp.duration,
                )
                interview = await repo.update(interview.id, {"transcript": transcript})
                await repo.create_cost_row(
                    interview_id=interview.id,
                    component=InterviewCostComponent.TRANSCRIPTION.value,
                    model=settings.transcription_model,
                    duration_seconds=transcript_resp.duration,
                    cost_usd=compute_transcription_cost_usd(
                        settings.transcription_model, transcript_resp.duration
                    ),
                )
                await db.commit()
                # repo.update() ends with session.refresh(), which expires the
                # job/employer/organization relationships that its own internal
                # get_by_id() had just eager-loaded — leaving the access below
                # dependent on an implicit lazy load that AsyncSession can't
                # reliably perform outside an explicit awaited call. Re-fetch
                # to guarantee those relationships are loaded before use.
                interview = await repo.get_by_id(interview.id)

            # Scoring is gated to Professional+ — transcript already saved above
            # regardless of plan tier.
            try:
                await BillingService(db).assert_professional_or_above(
                    interview.job.employer.organization_id
                )
            except PlanUpgradeRequiredException:
                logger.info(
                    "transcribe_and_score_interview: Interview %s on Starter plan — "
                    "skipping scoring",
                    interview_id,
                )
            else:
                job = interview.job
                job_context_parts = [
                    f"Title: {job.title}",
                    f"About the role: {job.about_the_role}"
                    if job.about_the_role
                    else "",
                    f"Key responsibilities: {job.key_responsibilities}"
                    if job.key_responsibilities
                    else "",
                    f"Requirements: {job.requirements}" if job.requirements else "",
                    f"Technical competencies: {job.technical_competencies}"
                    if job.technical_competencies
                    else "",
                ]
                job_context = "\n\n".join(p for p in job_context_parts if p)

                logger.info(
                    "transcribe_and_score_interview: org is Professional+ — scoring "
                    "transcript for interview %s",
                    interview_id,
                )
                ai_service = AnthropicCVExtractionService()
                try:
                    result = await ai_service.score_interview_transcript(
                        interview_brief=job.interview_brief or "",
                        transcript=transcript,
                        job_context=job_context,
                    )
                finally:
                    await ai_service._client.close()

                logger.info(
                    "transcribe_and_score_interview: scored interview %s -> %s/100",
                    interview_id,
                    result.score,
                )

                rationale_parts = [result.summary]
                if result.strengths:
                    rationale_parts.append(
                        "Strengths:\n"
                        + "\n".join(f"- {s}" for s in result.strengths)
                    )
                if result.weaknesses:
                    rationale_parts.append(
                        "Weaknesses:\n"
                        + "\n".join(f"- {w}" for w in result.weaknesses)
                    )
                if result.missing_evidence:
                    rationale_parts.append(
                        "Not covered in this interview:\n"
                        + "\n".join(f"- {m}" for m in result.missing_evidence)
                    )
                if result.contradictions:
                    rationale_parts.append(
                        "Contradictions:\n"
                        + "\n".join(f"- {c}" for c in result.contradictions)
                    )

                await repo.update(
                    interview.id,
                    {
                        "ai_score": result.score,
                        "ai_rationale": "\n\n".join(p for p in rationale_parts if p),
                        "ai_scored_at": datetime.now(UTC),
                    },
                )
                if result.input_tokens or result.output_tokens:
                    await repo.create_cost_row(
                        interview_id=interview.id,
                        component=InterviewCostComponent.SCORING.value,
                        model=settings.anthropic_model,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        cost_usd=compute_anthropic_cost_usd(
                            settings.anthropic_model,
                            result.input_tokens,
                            result.output_tokens,
                        ),
                    )
                await db.commit()

            await repo.update(interview.id, {"status": InterviewStatus.SCORED.value})
            await db.commit()

            # Notification failure must never undo a transcript/score that
            # already committed successfully above — this is a courtesy
            # side-effect, not part of the pipeline's success criteria.
            try:
                fields = await resolve_match_display_fields(
                    db, interview.talent_pool_profile, interview.job.employer_id
                )
                candidate_label = fields.get("name") or "A candidate"
                await NotificationRepository(db).create(
                    recipient_id=interview.job.employer_id,
                    type="AI_INTERVIEW_COMPLETED",
                    title=f"{candidate_label} completed their AI interview",
                    body=(
                        f"for {interview.job.title}. Open the Interview List to "
                        "review the transcript, score, and recording."
                    ),
                    entity_type="JOB",
                    entity_id=interview.job_id,
                )
                await db.commit()
            except Exception:
                logger.exception(
                    "transcribe_and_score_interview: failed to create completion "
                    "notification for interview %s — scoring itself already "
                    "succeeded and is unaffected",
                    interview_id,
                )

            logger.info(
                "transcribe_and_score_interview: finished interview %s", interview_id
            )
        except Exception:
            logger.exception(
                "transcribe_and_score_interview: failed for interview %s", interview_id
            )
            if mark_failed_on_error:
                # Last attempt — no more Celery retries coming, so this is
                # terminal. Only write FAILED here: writing it on every
                # attempt would make each retry's own UPLOADED-only guard
                # (above) skip the interview as a no-op, permanently
                # defeating autoretry after a single transient error.
                try:
                    await repo.update(
                        interview_id, {"status": InterviewStatus.FAILED.value}
                    )
                    await db.commit()
                except Exception:
                    logger.exception(
                        "transcribe_and_score_interview: failed to mark interview %s "
                        "as FAILED",
                        interview_id,
                    )
            else:
                logger.info(
                    "transcribe_and_score_interview: interview %s left as UPLOADED "
                    "for Celery retry (not the final attempt)",
                    interview_id,
                )
            raise
        finally:
            await engine.dispose()


@celery.task
def expire_interview_videos_task() -> None:
    """Celery Beat task — deletes R2 video objects past their retention window."""
    asyncio.run(_expire_interview_videos_async())


async def _expire_interview_videos_async() -> None:
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionLocal() as db:
        try:
            repo = InterviewRepository(db)
            expired = await repo.list_expired_with_video(datetime.now(UTC))
            if not expired:
                logger.info("expire_interview_videos: no expired videos to clean up")
                return

            logger.info(
                "expire_interview_videos: found %d expired video(s)", len(expired)
            )
            deleted = 0
            for interview in expired:
                try:
                    await get_storage_service().delete_file(interview.r2_key)
                    await repo.update(interview.id, {"r2_key": None})
                    await db.commit()
                    deleted += 1
                except Exception:
                    logger.exception(
                        "expire_interview_videos: failed to expire video for "
                        "interview %s — will retry on next sweep",
                        interview.id,
                    )
                    await db.rollback()

            logger.info(
                "expire_interview_videos: expired %d/%d video(s) this sweep",
                deleted,
                len(expired),
            )
        finally:
            await engine.dispose()


@celery.task
def reap_stale_interviews_task() -> None:
    """Celery Beat task — periodically marks orphaned in-progress interviews as failed.

    An interview stays IN_PROGRESS forever if the candidate closes the tab
    or their browser crashes mid-interview — the backend has no visibility
    into the live WebRTC session (it goes straight from the candidate's
    browser to OpenAI), so nothing else ever moves the row out of
    IN_PROGRESS. Left alone, this permanently misrepresents the interview
    as "currently happening" on the employer's interview list, with no
    signal that it needs a resend. See STALE_INTERVIEW_TIMEOUT for the
    staleness threshold.
    """
    asyncio.run(_reap_stale_interviews_async())


async def _reap_stale_interviews_async() -> None:
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionLocal() as db:
        try:
            repo = InterviewRepository(db)
            cutoff = datetime.now(UTC) - STALE_INTERVIEW_TIMEOUT
            stale_interviews = await repo.get_stale_in_progress_interviews(cutoff)
            if not stale_interviews:
                logger.info("reap_stale_interviews: no stale interviews to reap")
                return

            for interview in stale_interviews:
                await repo.update(interview.id, {"status": InterviewStatus.FAILED.value})
            await db.commit()

            logger.warning(
                "reap_stale_interviews: marked %d orphaned interview(s) failed",
                len(stale_interviews),
            )
        finally:
            await engine.dispose()
