"""Celery tasks for AI video interviews — email notifications, transcription, and scoring."""

import asyncio
import logging
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI
from sqlalchemy import select
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
from app.modules.interviews.credits import refund_if_unused, refund_interview_credits
from app.modules.interviews.enums import (
    STALE_INTERVIEW_TIMEOUT,
    InterviewCostComponent,
    InterviewStatus,
    TranscriptCheckStatus,
)
from app.modules.interviews.models import StrictInterviewRun
from app.modules.interviews.recording_merge import (
    concat_recordings,
    merge_key,
    part_key,
)
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.scoring_access import assert_can_score_interviews
from app.modules.interviews.transcript_check import compare_transcripts
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


# Shown to the scoring model ahead of a recording-derived transcript, which,
# unlike the browser's, cannot tell the interviewer from the candidate.
_UNLABELLED_TRANSCRIPT_NOTE = (
    "[This is an automatic transcript of the recording. It has no speaker "
    "labels: the AI interviewer's questions and the candidate's answers are "
    "mixed together. Only credit the candidate for what a candidate would be "
    "answering, not for the interviewer's own words.]\n\n"
)


async def _transcribe_recording(r2_key: str) -> tuple[str, float]:
    """Transcribe an interview recording on the server.

    Downloads the video from R2, extracts a small mono audio track with ffmpeg
    (Whisper rejects files over 25 MB) and transcribes it. Returns the text
    and the audio duration in seconds, which per-minute pricing needs.
    """
    video_bytes = await get_storage_service().download_file(r2_key)
    logger.info(
        "transcribe_recording: downloaded %d bytes (%s) — extracting audio",
        len(video_bytes),
        r2_key,
    )
    audio_bytes = await _extract_audio_for_whisper(video_bytes)
    logger.info(
        "transcribe_recording: extracted %d bytes of audio from %d bytes of video",
        len(audio_bytes),
        len(video_bytes),
    )

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        # verbose_json is what makes `.duration` available — whisper-1's
        # default response format doesn't return usage/duration data, and
        # per-minute Whisper pricing needs the audio duration.
        response = await openai_client.audio.transcriptions.create(
            file=("recording.mp3", audio_bytes),
            model=settings.transcription_model,
            response_format="verbose_json",
        )
    finally:
        await openai_client.close()

    return response.text, response.duration


async def _merge_recording_parts(db, repo, interview):
    """Join an interview's earlier recording parts and its final recording into one video.

    Returns the interview as it should be read from here on: with ``r2_key`` pointing at the
    joined video when a join happened, unchanged otherwise. Safe to run again after any
    failure: the output has its own key, the interview is only pointed at it (and the part
    count reset) in one commit, and the pieces are deleted only after that. A join that fails
    never blocks scoring: the final recording is still there, the parts stay in storage, and
    the failure is logged.
    """
    run = (
        await db.execute(
            select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview.id)
        )
    ).scalar_one_or_none()
    earlier_attempts = list(run.previous_recordings or []) if run is not None else []
    if (
        run is None
        or (run.recording_parts <= 0 and not earlier_attempts)
        or not interview.r2_key
    ):
        return interview

    storage = get_storage_service()
    # In the order they happened: the final recordings of earlier attempts (an interview the
    # employer reinstated), then this attempt's parts (kept across reloads), then its final one.
    used_keys: list[str] = []
    new_key: str | None = None
    try:
        pieces: list[bytes] = []
        wanted = [
            *earlier_attempts,
            *[part_key(interview.id, number) for number in range(1, run.recording_parts + 1)],
        ]
        for key in wanted:
            # A piece that was reserved but never uploaded (the browser went away) is skipped.
            if not await storage.get_object_size(key):
                logger.warning(
                    "merge_recording_parts: %s of interview %s is not in storage",
                    key,
                    interview.id,
                )
                continue
            pieces.append(await storage.download_file(key))
            used_keys.append(key)

        if pieces:
            pieces.append(await storage.download_file(interview.r2_key))
            try:
                joined = await concat_recordings(pieces)
            except RuntimeError:
                # The final recording can be nearly empty (a reload just after the last
                # answer), and a nearly empty file may not join. The earlier pieces are the
                # real interview, so join them alone rather than lose them.
                logger.warning(
                    "merge_recording_parts: the final recording of interview %s would not "
                    "join, joining the earlier pieces alone",
                    interview.id,
                    exc_info=True,
                )
                joined = await concat_recordings(pieces[:-1])
            new_key = merge_key(interview.id, run.attempt)
            await storage.upload_file(joined, new_key, "video/webm")
    except Exception:
        # Scoring does not depend on the video, so it carries on with the final recording.
        # The parts stay in storage so the join can be run again.
        logger.exception(
            "merge_recording_parts: could not join the recordings of interview %s", interview.id
        )
        return interview

    # The database change is not guarded: if it fails the task fails and runs again.
    old_key = interview.r2_key
    if new_key is not None:
        interview = await repo.update(interview.id, {"r2_key": new_key})
    run.recording_parts = 0
    run.previous_recordings = None
    await db.commit()

    for key in [*used_keys, *([old_key] if new_key is not None else [])]:
        try:
            await storage.delete_file(key)
        except Exception:
            logger.warning("merge_recording_parts: could not delete %s", key, exc_info=True)
    return interview


async def _record_scoring_cost(repo, interview_id, result) -> None:
    """Write the scoring cost row for a call that was actually billed,
    including failed attempts (a response we could not parse still cost tokens)."""
    if not (result.input_tokens or result.output_tokens):
        return
    await repo.create_cost_row(
        interview_id=interview_id,
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


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_ai_interview_invite_email(
    self,
    candidate_email: str,
    interview_url: str,
    job_title: str,
    company_name: str,
    strict: bool = False,
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
            strict=strict,
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
def transcribe_and_score_interview_task(
    self, interview_id: str, notify: bool = True
) -> None:
    """Transcribe an uploaded interview recording and score it against the job's brief.

    Transcription always runs and always saves, regardless of plan tier.
    Scoring (the LLM call) is gated to Professional+ orgs, mirroring how
    AI Talent Match CV scoring is gated — Starter interviews still end up
    SCORED with a transcript, just with no ai_score.

    Also used to score an interview that finished unscored (for example on the
    Starter plan) once the owner can have it scored. That run passes
    ``notify=False``, because the employer was already told it was completed.
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
            interview_id, mark_failed_on_error=is_final_attempt, notify=notify
        )
    )


async def _transcribe_and_score_interview_async(
    interview_id_str: str, mark_failed_on_error: bool = True, notify: bool = True
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

            # A strict interview whose page reloaded has earlier recordings uploaded as
            # separate parts. Join them into the one video the employer plays; the
            # steps below then read the joined recording.
            interview = await _merge_recording_parts(db, repo, interview)

            # The transcript the browser submitted (diarized, both speakers) is
            # captured on the candidate's own device, so it is checked against
            # a server-side transcription of the recording. A check already on
            # file means an earlier attempt did this; do not pay for Whisper twice.
            check = await repo.get_transcript_check(interview.id)
            # No recording left (retention expired) means nothing to cross-check
            # against; score the transcript we have rather than fail on a missing file.
            needs_server_transcript = not interview.transcript or (
                settings.interview_transcript_crosscheck_enabled
                and check is None
                and bool(interview.r2_key)
            )

            if needs_server_transcript:
                logger.info(
                    "transcribe_and_score_interview: transcribing the recording for "
                    "interview %s (submitted transcript present: %s, r2_key=%s)",
                    interview_id,
                    bool(interview.transcript),
                    interview.r2_key,
                )
                try:
                    server_text, audio_seconds = await _transcribe_recording(
                        interview.r2_key
                    )
                except Exception:
                    # With no submitted transcript there is nothing to fall back
                    # on, so fail (and retry) as before. With one, retry while
                    # attempts remain, then continue unverified rather than
                    # lose the interview over a failed cross-check.
                    if not interview.transcript or not mark_failed_on_error:
                        raise
                    logger.exception(
                        "transcribe_and_score_interview: cross-check transcription "
                        "failed for interview %s on the final attempt — continuing "
                        "with the submitted transcript, unverified",
                        interview_id,
                    )
                    await repo.create_transcript_check(
                        interview.id, TranscriptCheckStatus.UNAVAILABLE.value
                    )
                else:
                    await repo.create_cost_row(
                        interview_id=interview.id,
                        component=InterviewCostComponent.TRANSCRIPTION.value,
                        model=settings.transcription_model,
                        duration_seconds=audio_seconds,
                        cost_usd=compute_transcription_cost_usd(
                            settings.transcription_model, audio_seconds
                        ),
                    )
                    if not interview.transcript:
                        # No submitted transcript: the recording's own
                        # transcript becomes the transcript (no speaker labels).
                        await repo.update(interview.id, {"transcript": server_text})
                        # Recorded so a retry of a later step does not
                        # transcribe (and pay for) the same recording again.
                        await repo.create_transcript_check(
                            interview.id, TranscriptCheckStatus.SERVER_ONLY.value
                        )
                    else:
                        outcome = compare_transcripts(
                            interview.transcript,
                            server_text,
                            settings.interview_transcript_match_threshold,
                        )
                        await repo.create_transcript_check(
                            interview.id,
                            outcome.status,
                            match_score=outcome.match_score,
                            server_transcript=server_text,
                        )
                        logger.info(
                            "transcribe_and_score_interview: transcript check for "
                            "interview %s -> %s (match_score=%s, threshold=%s)",
                            interview_id,
                            outcome.status,
                            outcome.match_score,
                            settings.interview_transcript_match_threshold,
                        )
                await db.commit()
                # repo.update() ends with session.refresh(), which expires the
                # job/employer/organization relationships that its own internal
                # get_by_id() had just eager-loaded — leaving the access below
                # dependent on an implicit lazy load that AsyncSession can't
                # reliably perform outside an explicit awaited call. Re-fetch
                # to guarantee those relationships are loaded before use.
                interview = await repo.get_by_id(interview.id)
                check = await repo.get_transcript_check(interview.id)

            if (
                check is not None
                and check.status == TranscriptCheckStatus.MISMATCH.value
                and check.server_transcript
            ):
                # The submitted transcript does not match the recording, so it
                # is not scored. Score the recording's own transcript instead.
                transcript = _UNLABELLED_TRANSCRIPT_NOTE + check.server_transcript
            else:
                transcript = interview.transcript

            # Scoring is gated to Professional+ — transcript already saved above
            # regardless of plan tier.
            try:
                await assert_can_score_interviews(db, interview.job, interview.id)
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

                if result.failed:
                    # A failed call is not a score of 0. Never store it as
                    # one: an employer would read it as "performed terribly".
                    # Retry while attempts remain; on the last attempt leave
                    # the interview unscored so the recording and transcript
                    # stay reviewable.
                    await _record_scoring_cost(repo, interview.id, result)
                    await db.commit()
                    if not mark_failed_on_error:
                        raise RuntimeError(
                            f"Interview scoring failed for {interview_id}; retrying"
                        )
                    logger.error(
                        "transcribe_and_score_interview: scoring failed for "
                        "interview %s on the final attempt — leaving it unscored "
                        "(recording and transcript remain available)",
                        interview_id,
                    )
                else:
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
                            "ai_rationale": "\n\n".join(
                                p for p in rationale_parts if p
                            ),
                            "ai_scored_at": datetime.now(UTC),
                        },
                    )
                    await _record_scoring_cost(repo, interview.id, result)
                    await db.commit()

            await repo.update(interview.id, {"status": InterviewStatus.SCORED.value})
            await db.commit()

            # Notification failure must never undo a transcript/score that
            # already committed successfully above — this is a courtesy
            # side-effect, not part of the pipeline's success criteria.
            # Skipped when an already-completed interview is only being scored
            # later: the employer was told it was completed the first time.
            if notify:
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
                    # The failure is ours, so the customer is not charged for it.
                    # Kept apart from marking FAILED so a problem here can never
                    # hide the original error or undo that status.
                    try:
                        returned = await refund_interview_credits(db, interview_id)
                        await db.commit()
                        if returned:
                            logger.info(
                                "transcribe_and_score_interview: refunded %d "
                                "credit(s) for failed interview %s",
                                returned,
                                interview_id,
                            )
                    except Exception:
                        logger.exception(
                            "transcribe_and_score_interview: failed to refund "
                            "credits for failed interview %s",
                            interview_id,
                        )
                        await db.rollback()
            else:
                logger.info(
                    "transcribe_and_score_interview: interview %s left as UPLOADED "
                    "for Celery retry (not the final attempt)",
                    interview_id,
                )
            raise
        finally:
            await engine.dispose()


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def merge_interview_recording_task(self, interview_id: str) -> None:
    """Join the pieces of the recording of a strict interview that ended early (the parts kept
    across reloads, and the final recording), so the employer has one video to look at. An
    interview that finishes normally does this at the start of its scoring task; one that was
    ended or stopped is not scored, so it needs this on its own. Safe to run again."""
    asyncio.run(_merge_interview_recording_async(uuid.UUID(interview_id)))


async def _merge_interview_recording_async(interview_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True, poolclass=NullPool)
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionLocal() as db:
        try:
            repo = InterviewRepository(db)
            interview = await repo.get_by_id(interview_id)
            if interview is None:
                return
            await _merge_recording_parts(db, repo, interview)
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
def refund_unused_interviews_task() -> None:
    """Celery Beat task — gives credits back for invites that expired unopened.

    An interview is charged when it is first invited. If the link expires and the
    candidate never started the interview, the employer got nothing, so the
    credits are returned (a candidate who started and abandoned has already cost
    realtime money, and a resend is free, so that is not refunded). Idempotent: a
    refunded interview drops out of the query, and each refund re-checks under the
    interview's own lock, so a rerun or a worker restart mid-sweep is harmless.
    """
    asyncio.run(_refund_unused_interviews_async())


async def _refund_unused_interviews_async(limit: int = 200) -> int:
    """One sweep. Returns how many interviews were refunded."""
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    refunded = 0
    async with sessionLocal() as db:
        try:
            now = datetime.now(UTC)
            interview_ids = await InterviewRepository(
                db
            ).get_unused_expired_paid_interview_ids(now, limit)
            for interview_id in interview_ids:
                try:
                    returned = await refund_if_unused(db, interview_id, now)
                    await db.commit()
                    if returned:
                        refunded += 1
                except Exception:
                    logger.exception(
                        "refund_unused_interviews: failed to refund interview %s — "
                        "will retry on the next sweep",
                        interview_id,
                    )
                    await db.rollback()
            logger.info(
                "refund_unused_interviews: refunded %d of %d candidate(s) this sweep",
                refunded,
                len(interview_ids),
            )
        finally:
            await engine.dispose()
    return refunded


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
