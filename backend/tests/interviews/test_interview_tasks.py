"""Tests for the interview transcription+scoring Celery task.

External SDKs (OpenAI Whisper, Anthropic) and the ffmpeg-based audio
extraction are always mocked here — never invoked for real in this suite.
BillingService is exercised for real (it's in-repo logic, not an external
call), using real Plan/Subscription rows via the shared conftest factories.
"""

from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from app.core.config import settings
from app.modules.ai.schema import InterviewScoringResult
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.repository import InterviewRepository
from tests.conftest import (
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)

from .conftest import make_interview, make_talent_pool_profile


class _SameSessionCM:
    """Async context manager that hands back the test's own db_session
    instead of a new one — _transcribe_and_score_interview_async normally
    opens its own engine/session (correct for a real worker process), but
    that means it can never see data set up via the db_session fixture's
    own uncommitted transaction. Patched in via async_sessionmaker so the
    whole test runs on one connection, mirroring
    tests/ingestion/test_resumable_import.py."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _patch_engine_to_use_test_session(monkeypatch, db_session):
    monkeypatch.setattr(
        interviews_tasks,
        "create_async_engine",
        lambda *a, **k: AsyncMock(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        interviews_tasks,
        "async_sessionmaker",
        lambda *a, **k: (lambda: _SameSessionCM(db_session)),
    )


async def _setup_interview(db_session, transcript=None, plan_code="professional"):
    """Create an employer (+ org, + optional subscription), a job with an
    interview brief, a talent pool profile, and an UPLOADED interview ready
    for the task to pick up."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    if plan_code:
        await make_subscription_for(db_session, organization, plan_code=plan_code)

    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.UPLOADED.value,
        r2_key="interviews/test/recording.webm",
        transcript=transcript,
    )
    await db_session.commit()
    return employer, job, tp_profile, interview


def _mock_anthropic_service(monkeypatch, result=None, side_effect=None):
    mock_instance = MagicMock()
    mock_instance.score_interview_transcript = AsyncMock(
        return_value=result, side_effect=side_effect
    )
    mock_instance._client.close = AsyncMock()
    mock_class = Mock(return_value=mock_instance)
    monkeypatch.setattr(interviews_tasks, "AnthropicCVExtractionService", mock_class)
    return mock_instance


# ---------------------------------------------------------------------------
# Transcript presence branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcript_already_present_skips_download_and_whisper(
    db_session, monkeypatch
):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, _, _, interview = await _setup_interview(
        db_session, transcript="AI: Hi\n\nCandidate: Hello"
    )

    mock_storage = MagicMock()
    mock_storage.download_file = AsyncMock()
    monkeypatch.setattr(interviews_tasks, "get_storage_service", lambda: mock_storage)

    mock_extract = AsyncMock()
    monkeypatch.setattr(interviews_tasks, "_extract_audio_for_whisper", mock_extract)

    mock_openai_class = Mock()
    monkeypatch.setattr(interviews_tasks, "AsyncOpenAI", mock_openai_class)

    _mock_anthropic_service(
        monkeypatch, result=InterviewScoringResult(score=75, summary="Solid answers")
    )

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.id))

    mock_storage.download_file.assert_not_awaited()
    mock_extract.assert_not_awaited()
    mock_openai_class.assert_not_called()

    repo = InterviewRepository(db_session)
    updated = await repo.get_by_id(interview.id)
    assert updated.status == InterviewStatus.SCORED.value
    assert updated.ai_score == 75
    assert updated.transcript == "AI: Hi\n\nCandidate: Hello"


@pytest.mark.asyncio
async def test_no_transcript_triggers_download_extract_and_whisper(
    db_session, monkeypatch
):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, _, _, interview = await _setup_interview(db_session, transcript=None)

    mock_storage = MagicMock()
    mock_storage.download_file = AsyncMock(return_value=b"fake-video-bytes")
    monkeypatch.setattr(interviews_tasks, "get_storage_service", lambda: mock_storage)

    mock_extract = AsyncMock(return_value=b"fake-audio-bytes")
    monkeypatch.setattr(interviews_tasks, "_extract_audio_for_whisper", mock_extract)

    mock_openai_instance = MagicMock()
    mock_openai_instance.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(
            text="Candidate: I built a scheduler...", duration=123.4
        )
    )
    mock_openai_instance.close = AsyncMock()
    mock_openai_class = Mock(return_value=mock_openai_instance)
    monkeypatch.setattr(interviews_tasks, "AsyncOpenAI", mock_openai_class)

    _mock_anthropic_service(
        monkeypatch, result=InterviewScoringResult(score=60, summary="Decent")
    )

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.id))

    mock_storage.download_file.assert_awaited_once_with(interview.r2_key)
    mock_extract.assert_awaited_once_with(b"fake-video-bytes")
    mock_openai_instance.audio.transcriptions.create.assert_awaited_once_with(
        file=("recording.mp3", b"fake-audio-bytes"),
        model=interviews_tasks.settings.transcription_model,
        response_format="verbose_json",
    )

    repo = InterviewRepository(db_session)
    updated = await repo.get_by_id(interview.id)
    assert updated.transcript == "Candidate: I built a scheduler..."
    assert updated.status == InterviewStatus.SCORED.value
    assert updated.ai_score == 60

    from sqlalchemy import select

    from app.modules.interviews.models import InterviewCost

    result = await db_session.execute(
        select(InterviewCost).where(
            InterviewCost.interview_id == interview.id,
            InterviewCost.component == "transcription",
        )
    )
    cost_row = result.scalar_one()
    assert float(cost_row.duration_seconds) == 123.4
    assert cost_row.model == interviews_tasks.settings.transcription_model


# ---------------------------------------------------------------------------
# Plan gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_starter_plan_saves_transcript_but_skips_scoring(db_session, monkeypatch):
    # This env runs with PLAN_GATES_ENABLED=False (local/staging escape
    # hatch — see BillingService.get_effective_plan), which would make
    # every org resolve to Professional regardless of subscription. Force
    # gating on so this test actually exercises the Starter path.
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, _, _, interview = await _setup_interview(
        db_session, transcript="AI: Hi\n\nCandidate: Hello", plan_code=None
    )
    mock_anthropic = _mock_anthropic_service(
        monkeypatch, result=InterviewScoringResult(score=99)
    )

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.id))

    mock_anthropic.score_interview_transcript.assert_not_awaited()

    repo = InterviewRepository(db_session)
    updated = await repo.get_by_id(interview.id)
    assert updated.status == InterviewStatus.SCORED.value
    assert updated.ai_score is None
    assert updated.transcript == "AI: Hi\n\nCandidate: Hello"


@pytest.mark.asyncio
async def test_professional_plan_saves_transcript_and_score(db_session, monkeypatch):
    from app.core.ai_pricing import ANTHROPIC_TOKEN_PRICES

    _patch_engine_to_use_test_session(monkeypatch, db_session)
    # Pin to a model actually present in the pricing table — settings.anthropic_model
    # in the real .env may be a newer model not yet added there, which would
    # legitimately (and correctly) price as None rather than a wrong number.
    monkeypatch.setattr(
        interviews_tasks.settings, "anthropic_model", next(iter(ANTHROPIC_TOKEN_PRICES))
    )
    _, _, _, interview = await _setup_interview(
        db_session, transcript="AI: Hi\n\nCandidate: Hello", plan_code="professional"
    )
    _mock_anthropic_service(
        monkeypatch,
        result=InterviewScoringResult(
            score=88,
            summary="Strong candidate.",
            strengths=["Clear communication"],
            weaknesses=["Limited depth on scaling"],
            input_tokens=1500,
            output_tokens=400,
        ),
    )

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.id))

    repo = InterviewRepository(db_session)
    updated = await repo.get_by_id(interview.id)
    assert updated.status == InterviewStatus.SCORED.value
    assert updated.ai_score == 88
    assert "Strong candidate." in updated.ai_rationale
    assert "Clear communication" in updated.ai_rationale

    from sqlalchemy import select

    from app.modules.interviews.models import InterviewCost

    result = await db_session.execute(
        select(InterviewCost).where(
            InterviewCost.interview_id == interview.id,
            InterviewCost.component == "scoring",
        )
    )
    cost_row = result.scalar_one()
    assert cost_row.input_tokens == 1500
    assert cost_row.output_tokens == 400
    assert cost_row.cost_usd is not None


# ---------------------------------------------------------------------------
# Retry-defeat regression — the test that would have caught the bug fixed
# earlier this session (status flipping to FAILED on every attempt, not
# just the last one, which permanently no-oped every subsequent retry).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_final_attempt_leaves_status_uploaded_on_failure(
    db_session, monkeypatch
):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, _, _, interview = await _setup_interview(
        db_session, transcript="AI: Hi\n\nCandidate: Hello", plan_code="professional"
    )
    _mock_anthropic_service(
        monkeypatch, side_effect=RuntimeError("simulated transient failure")
    )

    with pytest.raises(RuntimeError):
        await interviews_tasks._transcribe_and_score_interview_async(
            str(interview.id), mark_failed_on_error=False
        )

    repo = InterviewRepository(db_session)
    updated = await repo.get_by_id(interview.id)
    assert updated.status == InterviewStatus.UPLOADED.value


@pytest.mark.asyncio
async def test_final_attempt_marks_failed_on_error(db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, _, _, interview = await _setup_interview(
        db_session, transcript="AI: Hi\n\nCandidate: Hello", plan_code="professional"
    )
    _mock_anthropic_service(
        monkeypatch, side_effect=RuntimeError("simulated transient failure")
    )

    with pytest.raises(RuntimeError):
        await interviews_tasks._transcribe_and_score_interview_async(
            str(interview.id), mark_failed_on_error=True
        )

    repo = InterviewRepository(db_session)
    updated = await repo.get_by_id(interview.id)
    assert updated.status == InterviewStatus.FAILED.value


def test_task_wrapper_is_final_attempt_arithmetic(monkeypatch):
    """The Celery-bound wrapper must only mark FAILED on the final attempt —
    verify the retries>=max_retries arithmetic that decides that, without a
    full Celery broker/worker."""
    captured = {}

    async def fake_async_impl(interview_id, mark_failed_on_error=True):
        captured["mark_failed_on_error"] = mark_failed_on_error

    monkeypatch.setattr(
        interviews_tasks, "_transcribe_and_score_interview_async", fake_async_impl
    )

    task = interviews_tasks.transcribe_and_score_interview_task

    task(str(uuid4()))  # no request context pushed -> retries defaults to 0
    assert captured["mark_failed_on_error"] is False

    task.push_request(retries=task.max_retries)
    try:
        task(str(uuid4()))
    finally:
        task.pop_request()
    assert captured["mark_failed_on_error"] is True


# ---------------------------------------------------------------------------
# reap_stale_interviews — the orphaned-IN_PROGRESS-interview sweep
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reap_marks_stale_in_progress_interview_failed(db_session, monkeypatch):
    """An interview stuck IN_PROGRESS with no activity past the staleness
    window (closed tab / crashed browser mid-interview) must be flipped to
    FAILED — this is the actual bug the reaper closes."""
    from datetime import UTC, datetime, timedelta

    _patch_engine_to_use_test_session(monkeypatch, db_session)

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    stale_cutoff_breach = datetime.now(UTC) - timedelta(hours=3)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        updated_at=stale_cutoff_breach,
    )

    await interviews_tasks._reap_stale_interviews_async()

    repo = InterviewRepository(db_session)
    refreshed = await repo.get_by_id(interview.id)
    assert refreshed.status == InterviewStatus.FAILED.value


@pytest.mark.asyncio
async def test_reap_leaves_recently_active_in_progress_interview_alone(
    db_session, monkeypatch
):
    """A genuinely in-progress interview (recent activity) must not be
    touched — only staleness, not the IN_PROGRESS status alone, is the
    trigger."""
    _patch_engine_to_use_test_session(monkeypatch, db_session)

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session, job.id, tp_profile.id, status=InterviewStatus.IN_PROGRESS.value
    )

    await interviews_tasks._reap_stale_interviews_async()

    repo = InterviewRepository(db_session)
    refreshed = await repo.get_by_id(interview.id)
    assert refreshed.status == InterviewStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_reap_leaves_non_in_progress_statuses_alone(db_session, monkeypatch):
    """A stale-looking PENDING/UPLOADED/SCORED interview isn't the reaper's
    concern — only IN_PROGRESS represents an abandoned live session."""
    from datetime import UTC, datetime, timedelta

    _patch_engine_to_use_test_session(monkeypatch, db_session)

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    stale_cutoff_breach = datetime.now(UTC) - timedelta(hours=3)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.PENDING.value,
        updated_at=stale_cutoff_breach,
    )

    await interviews_tasks._reap_stale_interviews_async()

    repo = InterviewRepository(db_session)
    refreshed = await repo.get_by_id(interview.id)
    assert refreshed.status == InterviewStatus.PENDING.value
