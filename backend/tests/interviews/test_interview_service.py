"""Tests for InterviewService — invite lifecycle, ownership/token resolution,
send/resend flows, and the CV-assessment fallback used on the employer review UI.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import (
    InterviewNotFound,
    JobNotFoundError,
    PermissionDeniedException,
    ValidationException,
)
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import Interview
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from tests.conftest import make_employer, make_job

from .conftest import (
    make_application,
    make_candidate_profile,
    make_candidate_user,
    make_interview,
    make_interview_list_entry,
    make_talent_pool_profile,
)

# ---------------------------------------------------------------------------
# create_invite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_invite_returns_none_without_interview_brief(db_session):
    """No interview_brief configured on the job -> no invite is created."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief=None)
    db_session.add(job)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        result = await service.create_invite(job, uuid4())
    finally:
        await service.close()

    assert result is None


@pytest.mark.parametrize(
    "status", [InterviewStatus.UPLOADED.value, InterviewStatus.SCORED.value]
)
@pytest.mark.asyncio
async def test_create_invite_returns_none_when_already_completed(db_session, status):
    """An interview that already ended in UPLOADED/SCORED has nothing new to invite to."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview(db_session, job.id, tp_profile.id, status=status)

    service = InterviewService(db_session)
    try:
        result = await service.create_invite(job, tp_profile.id)
    finally:
        await service.close()

    assert result is None


@pytest.mark.asyncio
async def test_create_invite_success_returns_interview_and_url(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)

    service = InterviewService(db_session)
    try:
        result = await service.create_invite(job, tp_profile.id)
    finally:
        await service.close()

    assert result is not None
    interview, url = result
    assert interview.token is not None
    assert url == f"{settings.app_url}/interview/{interview.token}"


@pytest.mark.asyncio
async def test_create_invite_resend_resets_restart_lock(db_session):
    """A resend is a deliberate employer action, not the candidate's own
    reload — it must reset session_start_count so a candidate blocked by
    the restart lock (see _start_session) actually gets the manual
    override the error message promises, and a stuck IN_PROGRESS
    interview goes back to PENDING so it reads as a fresh start."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        session_start_count=2,
        reset_requested_at=datetime.now(UTC),
    )

    service = InterviewService(db_session)
    try:
        result = await service.create_invite(job, tp_profile.id)
    finally:
        await service.close()

    assert result is not None
    interview, _url = result
    assert interview.session_start_count == 0
    assert interview.status == InterviewStatus.PENDING.value
    assert interview.reset_requested_at is None


# ---------------------------------------------------------------------------
# _resolve_owned_interview
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_owned_interview_rejects_other_candidates_application(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    owner = make_candidate_user()
    intruder = make_candidate_user()
    db_session.add_all([owner, intruder])
    await db_session.flush()

    application = await make_application(db_session, owner.id, job.id)

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service._resolve_owned_interview(application.id, intruder.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_resolve_owned_interview_rejects_uninvited_candidate(db_session):
    """Candidate has a real application but was never added to the interview list."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    candidate_user = make_candidate_user()
    db_session.add(candidate_user)
    await db_session.flush()
    await make_candidate_profile(db_session, candidate_user)
    application = await make_application(db_session, candidate_user.id, job.id)
    # No talent pool profile / InterviewListEntry created — not invited.

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service._resolve_owned_interview(application.id, candidate_user.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_resolve_owned_interview_succeeds_once_invited(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    candidate_user = make_candidate_user()
    db_session.add(candidate_user)
    await db_session.flush()
    candidate_profile = await make_candidate_profile(db_session, candidate_user)
    tp_profile = await make_talent_pool_profile(
        db_session, added_by_id=employer.id, candidate_profile_id=candidate_profile.id
    )
    application = await make_application(db_session, candidate_user.id, job.id)
    await make_interview_list_entry(db_session, employer.id, tp_profile.id, job.id)
    interview = await make_interview(db_session, job.id, tp_profile.id)

    service = InterviewService(db_session)
    try:
        resolved = await service._resolve_owned_interview(
            application.id, candidate_user.id
        )
    finally:
        await service.close()

    assert resolved.id == interview.id


# ---------------------------------------------------------------------------
# _resolve_interview_by_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_interview_by_token_unknown_token_raises(db_session):
    service = InterviewService(db_session)
    try:
        with pytest.raises(InterviewNotFound):
            await service._resolve_interview_by_token("no-such-token")
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_resolve_interview_by_token_expired_raises(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        token="expired-token",
        token_expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException):
            await service._resolve_interview_by_token("expired-token")
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_resolve_interview_by_token_valid_succeeds(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview_list_entry(db_session, employer.id, tp_profile.id, job.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        token="valid-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    service = InterviewService(db_session)
    try:
        resolved = await service._resolve_interview_by_token("valid-token")
    finally:
        await service.close()

    assert resolved.id == interview.id


@pytest.mark.asyncio
async def test_resolve_interview_by_token_rejects_after_removal_from_interview_list(
    db_session,
):
    """The whole point of this check — an employer removing a candidate from
    the interview list must revoke the token immediately, not leave it
    valid for up to ~14 more days (see _INVITE_TOKEN_EXPIRY_DAYS)."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    # No InterviewListEntry created — simulates a candidate who was removed
    # (or never on the list) despite still holding a live, unexpired token.
    await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        token="removed-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=1),
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service._resolve_interview_by_token("removed-token")
    finally:
        await service.close()


# ---------------------------------------------------------------------------
# send_invite / send_invites_to_all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_invite_rejects_non_owning_employer(db_session):
    owner = make_employer()
    intruder = make_employer()
    db_session.add_all([owner, intruder])
    await db_session.flush()
    job = make_job(owner.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=owner.id)

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service.send_invite(intruder.id, job.id, tp_profile.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_send_invite_raises_for_unknown_job(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        with pytest.raises(JobNotFoundError):
            await service.send_invite(employer.id, uuid4(), uuid4())
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_send_invites_to_all_rejects_non_owning_employer(db_session):
    owner = make_employer()
    intruder = make_employer()
    db_session.add_all([owner, intruder])
    await db_session.flush()
    job = make_job(owner.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service.send_invites_to_all(intruder.id, job.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_send_invites_to_all_raises_for_unknown_job(db_session):
    """Regression test for the missing job-not-found guard fixed in this phase."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        with pytest.raises(JobNotFoundError):
            await service.send_invites_to_all(employer.id, uuid4())
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_send_invite_skips_without_raising_when_no_email(db_session):
    """A sourced-only profile with no resolvable email is skipped, not an error."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer.id, job.id, tp_profile.id)
    finally:
        await service.close()

    assert result == {"sent": False, "reason": "No email on file for this candidate"}


@pytest.mark.asyncio
async def test_send_invite_resend_reuses_same_interview_row(db_session, monkeypatch):
    """A resend for the same (job_id, talent_pool_profile_id) must not create
    a second Interview row — it reissues the token on the existing one."""
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module

    mock_email_task = Mock()
    mock_email_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "send_ai_interview_invite_email", mock_email_task
    )

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(
        db_session, added_by_id=employer.id, override_email="candidate@example.com"
    )

    service = InterviewService(db_session)
    try:
        first = await service.send_invite(employer.id, job.id, tp_profile.id)
        second = await service.send_invite(employer.id, job.id, tp_profile.id)
    finally:
        await service.close()

    assert first["sent"] is True
    assert second["sent"] is True
    assert mock_email_task.delay.call_count == 2

    rows = (
        (
            await db_session.execute(
                select(Interview).where(
                    Interview.job_id == job.id,
                    Interview.talent_pool_profile_id == tp_profile.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# _resolve_cv_assessment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_cv_assessment_returns_application_score(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    candidate_user = make_candidate_user()
    db_session.add(candidate_user)
    await db_session.flush()
    application = await make_application(
        db_session,
        candidate_user.id,
        job.id,
        ai_score=80,
        ai_strengths=["Python"],
        ai_weaknesses=["SQL"],
        ai_fit_summary="Good fit",
    )
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview(
        db_session, job.id, tp_profile.id, application_id=application.id
    )

    repo = InterviewRepository(db_session)
    interview = await repo.get_by_job_and_profile(job.id, tp_profile.id)

    service = InterviewService(db_session)
    try:
        score, strengths, weaknesses, summary = await service._resolve_cv_assessment(
            interview, job
        )
    finally:
        await service.close()

    assert score == 80
    assert strengths == ["Python"]
    assert weaknesses == ["SQL"]
    assert summary == "Good fit"


@pytest.mark.asyncio
async def test_resolve_cv_assessment_nulls_when_application_has_no_score(db_session):
    """application_id is set but that application was never scored — must not
    fall through to the talent-pool profile's score."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    candidate_user = make_candidate_user()
    db_session.add(candidate_user)
    await db_session.flush()
    application = await make_application(db_session, candidate_user.id, job.id)
    tp_profile = await make_talent_pool_profile(
        db_session, added_by_id=employer.id, ai_score=55, ai_score_job_hash="whatever"
    )
    await make_interview(
        db_session, job.id, tp_profile.id, application_id=application.id
    )

    repo = InterviewRepository(db_session)
    interview = await repo.get_by_job_and_profile(job.id, tp_profile.id)

    service = InterviewService(db_session)
    try:
        result = await service._resolve_cv_assessment(interview, job)
    finally:
        await service.close()

    assert result == (None, None, None, None)


@pytest.mark.asyncio
async def test_resolve_cv_assessment_falls_back_to_talent_pool_score_when_hash_matches(
    db_session,
):
    from app.modules.ai.scoring_service import hash_job_scoring_inputs
    from app.modules.jobs.schemas import build_full_description

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(
        employer.id,
        interview_brief="Ask about distributed systems.",
        about_the_role="Build things",
        key_responsibilities="Write code",
        requirements="Python experience",
        technical_competencies="Python, SQL",
    )
    db_session.add(job)
    await db_session.flush()

    description = build_full_description(
        about_the_role=job.about_the_role,
        key_responsibilities=job.key_responsibilities,
        requirements=job.requirements,
        preferred_certifications=job.preferred_certifications,
        technical_competencies=job.technical_competencies,
        what_we_offer=job.what_we_offer,
        legacy_description=job.description,
    )
    current_hash = hash_job_scoring_inputs(
        description, job.required_skills or [], job.seniority_level
    )

    tp_profile = await make_talent_pool_profile(
        db_session,
        added_by_id=employer.id,
        ai_score=70,
        ai_strengths=["Communication"],
        ai_weaknesses=["Depth"],
        ai_fit_summary="Solid",
        ai_score_job_hash=current_hash,
    )
    await make_interview(db_session, job.id, tp_profile.id)

    repo = InterviewRepository(db_session)
    interview = await repo.get_by_job_and_profile(job.id, tp_profile.id)

    service = InterviewService(db_session)
    try:
        score, strengths, weaknesses, summary = await service._resolve_cv_assessment(
            interview, job
        )
    finally:
        await service.close()

    assert score == 70
    assert strengths == ["Communication"]
    assert weaknesses == ["Depth"]
    assert summary == "Solid"


@pytest.mark.asyncio
async def test_resolve_cv_assessment_nulls_when_hash_is_stale(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(
        db_session,
        added_by_id=employer.id,
        ai_score=70,
        ai_score_job_hash="stale-hash-from-a-different-job",
    )
    await make_interview(db_session, job.id, tp_profile.id)

    repo = InterviewRepository(db_session)
    interview = await repo.get_by_job_and_profile(job.id, tp_profile.id)

    service = InterviewService(db_session)
    try:
        result = await service._resolve_cv_assessment(interview, job)
    finally:
        await service.close()

    assert result == (None, None, None, None)


# ---------------------------------------------------------------------------
# Realtime cost recording on complete_upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_complete_upload_records_realtime_cost(db_session, monkeypatch):
    """Real accumulated Realtime usage reported by the frontend must land as
    an InterviewCost row with the raw usage_detail round-tripped through JSONB."""
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module
    from app.modules.interviews.models import InterviewCost
    from app.modules.interviews.schema import RealtimeUsageDetail

    mock_task = Mock()
    mock_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "transcribe_and_score_interview_task", mock_task
    )

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        r2_key="interviews/test/recording.webm",
    )

    usage = RealtimeUsageDetail(
        input_tokens=2000,
        output_tokens=800,
        input_token_details={"text_tokens": 200, "audio_tokens": 1800},
        output_token_details={"text_tokens": 50, "audio_tokens": 750},
    )

    service = InterviewService(db_session)
    try:
        await service._complete_upload(interview, realtime_usage=usage)
    finally:
        await service.close()

    assert mock_task.delay.call_count == 1

    result = await db_session.execute(
        select(InterviewCost).where(
            InterviewCost.interview_id == interview.id,
            InterviewCost.component == "realtime",
        )
    )
    cost_row = result.scalar_one()
    assert cost_row.input_tokens == 2000
    assert cost_row.output_tokens == 800
    assert cost_row.usage_detail["input_token_details"]["audio_tokens"] == 1800
    assert cost_row.model == settings.realtime_model


@pytest.mark.asyncio
async def test_complete_upload_skips_realtime_cost_when_no_usage(db_session, monkeypatch):
    """No realtime_usage (or all-zero usage) must not write a cost row at all."""
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module
    from app.modules.interviews.models import InterviewCost

    mock_task = Mock()
    mock_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "transcribe_and_score_interview_task", mock_task
    )

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        r2_key="interviews/test/recording.webm",
    )

    service = InterviewService(db_session)
    try:
        await service._complete_upload(interview, realtime_usage=None)
    finally:
        await service.close()

    result = await db_session.execute(
        select(InterviewCost).where(InterviewCost.interview_id == interview.id)
    )
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# _start_session — restart lock (see AskUserQuestion: 1 free restart, then blocked)
# ---------------------------------------------------------------------------


def _mock_realtime_client_secret():
    """Build a mock in the shape InterviewService._start_session reads
    off client_secrets.create()'s response."""
    from unittest.mock import AsyncMock, Mock

    mock_secret = Mock(value="ek_test_secret", expires_at=int(datetime.now(UTC).timestamp()) + 600)
    mock_client_secrets = Mock()
    mock_client_secrets.create = AsyncMock(return_value=mock_secret)
    mock_realtime = Mock(client_secrets=mock_client_secrets)
    mock_client = Mock(realtime=mock_realtime)
    mock_client.close = AsyncMock()
    return mock_client


@pytest.mark.asyncio
async def test_start_session_first_call_succeeds_and_increments_count(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(db_session, job.id, tp_profile.id)
    assert interview.session_start_count == 0

    service = InterviewService(db_session)
    service._client = _mock_realtime_client_secret()
    try:
        # interview.job is lazy-loaded — refetch through the repo so the
        # relationship is populated, same as the real call chain does.
        interview = await InterviewRepository(db_session).get_by_id(interview.id)
        result = await service._start_session(interview)
    finally:
        await service.close()

    assert result.client_secret == "ek_test_secret"
    refreshed = await InterviewRepository(db_session).get_by_id(interview.id)
    assert refreshed.session_start_count == 1
    assert refreshed.status == InterviewStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_start_session_one_restart_is_tolerated(db_session):
    """A reload after the first session (session_start_count == 1) — the
    one free restart — must still succeed."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        session_start_count=1,
    )

    service = InterviewService(db_session)
    service._client = _mock_realtime_client_secret()
    try:
        interview = await InterviewRepository(db_session).get_by_id(interview.id)
        result = await service._start_session(interview)
    finally:
        await service.close()

    assert result.client_secret == "ek_test_secret"
    refreshed = await InterviewRepository(db_session).get_by_id(interview.id)
    assert refreshed.session_start_count == 2


@pytest.mark.asyncio
async def test_start_session_second_restart_is_blocked(db_session):
    """A second reload (session_start_count already == 2) must be rejected
    without minting a new Realtime session — this is the actual fix for
    the reported bug: unlimited restarts after hearing the AI's questions."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        session_start_count=2,
    )

    service = InterviewService(db_session)
    mock_client = _mock_realtime_client_secret()
    service._client = mock_client
    try:
        interview = await InterviewRepository(db_session).get_by_id(interview.id)
        with pytest.raises(ValidationException):
            await service._start_session(interview)
    finally:
        await service.close()

    mock_client.realtime.client_secrets.create.assert_not_called()
    refreshed = await InterviewRepository(db_session).get_by_id(interview.id)
    assert refreshed.session_start_count == 2


# ---------------------------------------------------------------------------
# _request_reset — the dedicated "notify employer" action for a candidate
# blocked by the restart lock (see test_start_session_second_restart_is_blocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_reset_rejected_when_interview_not_locked(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        session_start_count=1,
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException):
            await service._request_reset(interview)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_request_reset_notifies_employer_first_time(db_session, monkeypatch):
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module
    from app.modules.notifications.models import Notification

    mock_task = Mock()
    mock_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "send_interview_restart_request_email", mock_task
    )

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        session_start_count=2,
    )

    service = InterviewService(db_session)
    try:
        interview = await InterviewRepository(db_session).get_by_id(interview.id)
        result = await service._request_reset(interview)
    finally:
        await service.close()

    assert result == {"sent": True, "already_requested": False}
    assert mock_task.delay.call_count == 1
    assert mock_task.delay.call_args.kwargs["employer_email"] == employer.email

    refreshed = await InterviewRepository(db_session).get_by_id(interview.id)
    assert refreshed.reset_requested_at is not None

    notif_result = await db_session.execute(
        select(Notification).where(Notification.recipient_id == employer.id)
    )
    notification = notif_result.scalar_one_or_none()
    assert notification is not None
    assert notification.entity_type == "JOB"
    assert notification.entity_id == job.id
    assert notification.context["job_id"] == str(job.id)
    assert notification.context["talent_pool_profile_id"] == str(tp_profile.id)
    assert notification.context["candidate_name"]


@pytest.mark.asyncio
async def test_request_reset_is_idempotent_on_repeat_click(db_session, monkeypatch):
    """A second click before the employer resends must not re-notify them."""
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module

    mock_task = Mock()
    mock_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "send_interview_restart_request_email", mock_task
    )

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        session_start_count=2,
        reset_requested_at=datetime.now(UTC),
    )

    service = InterviewService(db_session)
    try:
        result = await service._request_reset(interview)
    finally:
        await service.close()

    assert result == {"sent": False, "already_requested": True}
    mock_task.delay.assert_not_called()
