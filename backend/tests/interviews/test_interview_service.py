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


@pytest.fixture(autouse=True)
def _recording_exists_in_storage(monkeypatch):
    """_complete_upload now checks the recording exists in storage. Default every
    test in this file to 'present'; tests of the guard itself override it with
    _patch_recording_size, and never touch real R2."""
    from unittest.mock import AsyncMock, MagicMock

    from app.modules.interviews import service as interview_service_module

    storage = MagicMock()
    storage.get_object_size = AsyncMock(return_value=1024)
    monkeypatch.setattr(
        interview_service_module, "get_storage_service", lambda: storage
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
            await service.send_invite(intruder, job.id, tp_profile.id)
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
            await service.send_invite(employer, uuid4(), uuid4())
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
            await service.send_invites_to_all(intruder, job.id)
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
            await service.send_invites_to_all(employer, uuid4())
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
        result = await service.send_invite(employer, job.id, tp_profile.id)
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
        first = await service.send_invite(employer, job.id, tp_profile.id)
        second = await service.send_invite(employer, job.id, tp_profile.id)
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
# get_interview_link (copy the link instead of emailing it)
# ---------------------------------------------------------------------------


async def _job_and_profile(db_session, **job_overrides):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job_fields = {"interview_brief": "Ask about distributed systems."}
    job_fields.update(job_overrides)
    job = make_job(employer.id, **job_fields)
    db_session.add(job)
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    return employer, job, profile


@pytest.mark.asyncio
async def test_get_interview_link_works_with_no_email_and_sends_nothing(
    db_session, monkeypatch
):
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module

    email_task = Mock()
    monkeypatch.setattr(
        interview_service_module, "send_ai_interview_invite_email", email_task
    )
    employer, job, profile = await _job_and_profile(db_session)

    service = InterviewService(db_session)
    try:
        result = await service.get_interview_link(employer, job.id, profile.id)
        interview = await InterviewRepository(db_session).get_by_job_and_profile(
            job.id, profile.id
        )
    finally:
        await service.close()

    assert result["interview_url"] == f"{settings.app_url}/interview/{interview.token}"
    email_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_get_interview_link_twice_returns_the_same_link(db_session):
    employer, job, profile = await _job_and_profile(db_session)

    service = InterviewService(db_session)
    try:
        first = await service.get_interview_link(employer, job.id, profile.id)
        second = await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()

    assert first == second


@pytest.mark.asyncio
async def test_get_interview_link_does_not_disturb_a_candidate_mid_interview(
    db_session,
):
    employer, job, profile = await _job_and_profile(db_session)
    interview = await make_interview(
        db_session,
        job.id,
        profile.id,
        status=InterviewStatus.IN_PROGRESS.value,
        token="live-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=3),
        session_start_count=1,
    )

    service = InterviewService(db_session)
    try:
        result = await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()

    await db_session.refresh(interview)
    assert result["interview_url"].endswith("/interview/live-token")
    assert interview.token == "live-token"
    assert interview.status == InterviewStatus.IN_PROGRESS.value
    assert interview.session_start_count == 1


@pytest.mark.asyncio
async def test_get_interview_link_reissues_an_expired_link(db_session):
    employer, job, profile = await _job_and_profile(db_session)
    interview = await make_interview(
        db_session,
        job.id,
        profile.id,
        token="old-token",
        token_expires_at=datetime.now(UTC) - timedelta(days=1),
    )

    service = InterviewService(db_session)
    try:
        result = await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()

    await db_session.refresh(interview)
    assert interview.token != "old-token"
    assert result["interview_url"].endswith(f"/interview/{interview.token}")
    assert interview.token_expires_at > datetime.now(UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [InterviewStatus.UPLOADED.value, InterviewStatus.SCORED.value]
)
async def test_get_interview_link_refuses_a_finished_interview(db_session, status):
    employer, job, profile = await _job_and_profile(db_session)
    await make_interview(
        db_session,
        job.id,
        profile.id,
        status=status,
        token="done-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=3),
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException):
            await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_get_interview_link_requires_an_interview_brief(db_session):
    employer, job, profile = await _job_and_profile(db_session, interview_brief=None)

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException):
            await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_get_interview_link_refuses_someone_who_cannot_manage_the_job(
    db_session,
):
    _owner, job, profile = await _job_and_profile(db_session)
    outsider = make_employer()
    db_session.add(outsider)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service.get_interview_link(outsider, job.id, profile.id)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_get_interview_link_unknown_job(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        with pytest.raises(JobNotFoundError):
            await service.get_interview_link(employer, uuid4(), uuid4())
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_get_interview_link_respects_the_off_switch(db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_enabled", False)
    employer, job, profile = await _job_and_profile(db_session)

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException) as raised:
            await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()

    assert raised.value.code == "AI_INTERVIEWS_DISABLED"


@pytest.mark.asyncio
async def test_get_interview_link_respects_the_daily_invite_limit(
    db_session, monkeypatch
):
    monkeypatch.setattr(settings, "interview_daily_invite_limit", 1)
    employer, job, first_profile = await _job_and_profile(db_session)
    second_profile = await make_talent_pool_profile(
        db_session, added_by_id=employer.id
    )

    service = InterviewService(db_session)
    try:
        await service.get_interview_link(employer, job.id, first_profile.id)
        with pytest.raises(ValidationException):
            await service.get_interview_link(employer, job.id, second_profile.id)
        # The profile that already has an interview is not a new invite, so it
        # still gets its link back.
        again = await service.get_interview_link(employer, job.id, first_profile.id)
    finally:
        await service.close()

    assert again["interview_url"]


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
# complete_upload guards — status, and the recording must really exist
# ---------------------------------------------------------------------------


def _patch_recording_size(monkeypatch, size=None, error=None):
    """Make the storage check report `size` bytes (None = object missing), or
    raise `error` when storage itself cannot be asked."""
    from unittest.mock import AsyncMock, MagicMock

    from app.modules.interviews import service as interview_service_module

    storage = MagicMock()
    storage.get_object_size = AsyncMock(return_value=size, side_effect=error)
    monkeypatch.setattr(
        interview_service_module, "get_storage_service", lambda: storage
    )
    return storage


def _patch_scoring_task(monkeypatch):
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module

    mock_task = Mock()
    mock_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "transcribe_and_score_interview_task", mock_task
    )
    return mock_task


async def _make_interview_in_status(db_session, status, **overrides):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    return await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        status=status,
        r2_key="interviews/test/recording.webm",
        **overrides,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [InterviewStatus.UPLOADED.value, InterviewStatus.SCORED.value]
)
async def test_complete_upload_is_a_noop_when_already_completed(
    db_session, monkeypatch, status
):
    """A replayed or retried 'complete' must not reset the status, re-queue
    scoring, or let a later request overwrite the saved transcript and score."""
    mock_task = _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, size=1024)
    interview = await _make_interview_in_status(
        db_session,
        status,
        transcript="original transcript",
        ai_score=80,
    )

    service = InterviewService(db_session)
    try:
        result = await service._complete_upload(interview, transcript="forged text")
    finally:
        await service.close()

    mock_task.delay.assert_not_called()
    assert result.status == status
    assert result.transcript == "original transcript"
    assert result.ai_score == 80


@pytest.mark.asyncio
async def test_complete_upload_sees_a_concurrent_completion_through_a_stale_copy(
    db_session, monkeypatch
):
    """Two 'complete' calls arriving together both load IN_PROGRESS. Once the
    first has committed, the second must read the real status from the database
    and do nothing, instead of trusting its stale copy and queueing a second
    scoring run."""
    from sqlalchemy import update

    mock_task = _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, size=1024)
    interview = await _make_interview_in_status(
        db_session, InterviewStatus.IN_PROGRESS.value
    )
    assert interview.status == InterviewStatus.IN_PROGRESS.value  # the stale copy

    # The other request finishes: the database now says UPLOADED, while this
    # request's loaded copy still says IN_PROGRESS.
    await db_session.execute(
        update(Interview)
        .where(Interview.id == interview.id)
        .values(status=InterviewStatus.UPLOADED.value)
        .execution_options(synchronize_session=False)
    )
    assert interview.status == InterviewStatus.IN_PROGRESS.value

    service = InterviewService(db_session)
    try:
        result = await service._complete_upload(interview, transcript="second call")
    finally:
        await service.close()

    mock_task.delay.assert_not_called()
    assert result.status == InterviewStatus.UPLOADED.value
    assert result.transcript is None


@pytest.mark.asyncio
async def test_complete_upload_locks_the_interview_row(db_session, monkeypatch):
    """The lock is what makes a simultaneous second call wait for the first."""
    from sqlalchemy import event

    _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, size=1024)
    interview = await _make_interview_in_status(
        db_session, InterviewStatus.IN_PROGRESS.value
    )

    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    connection = (await db_session.connection()).sync_connection
    event.listen(connection, "before_cursor_execute", capture)
    try:
        service = InterviewService(db_session)
        try:
            await service._complete_upload(interview)
        finally:
            await service.close()
    finally:
        event.remove(connection, "before_cursor_execute", capture)

    assert any(
        "FROM interviews" in s and "FOR UPDATE" in s for s in statements
    ), "completing an upload must lock the interview row"


@pytest.mark.asyncio
async def test_complete_upload_rejects_failed_interview(db_session, monkeypatch):
    mock_task = _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, size=1024)
    interview = await _make_interview_in_status(
        db_session, InterviewStatus.FAILED.value
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException):
            await service._complete_upload(interview)
    finally:
        await service.close()

    mock_task.delay.assert_not_called()
    assert interview.status == InterviewStatus.FAILED.value


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [None, 0])
async def test_complete_upload_rejects_missing_or_empty_recording(
    db_session, monkeypatch, size
):
    """r2_key is set when the upload URL is issued, so it proves nothing. A
    candidate who never uploaded (or uploaded 0 bytes) must not become UPLOADED."""
    mock_task = _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, size=size)
    interview = await _make_interview_in_status(
        db_session, InterviewStatus.IN_PROGRESS.value
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException) as exc_info:
            await service._complete_upload(interview, transcript="AI: Hi")
    finally:
        await service.close()

    # A specific code lets the candidate page re-upload instead of just retrying.
    assert exc_info.value.code == "RECORDING_NOT_RECEIVED"
    mock_task.delay.assert_not_called()
    assert interview.status == InterviewStatus.IN_PROGRESS.value
    assert interview.transcript is None


@pytest.mark.asyncio
async def test_complete_upload_allows_completion_when_storage_cannot_be_checked(
    db_session, monkeypatch
):
    """An R2 outage or a missing HEAD permission must not cost a real
    candidate their interview: only a definitive 'missing' blocks."""
    mock_task = _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, error=RuntimeError("storage unreachable"))
    interview = await _make_interview_in_status(
        db_session, InterviewStatus.IN_PROGRESS.value
    )

    service = InterviewService(db_session)
    try:
        result = await service._complete_upload(interview, transcript="AI: Hi")
    finally:
        await service.close()

    assert result.status == InterviewStatus.UPLOADED.value
    mock_task.delay.assert_called_once()


# ---------------------------------------------------------------------------
# Organization-level ownership: teammates act on each other's jobs
# ---------------------------------------------------------------------------


async def _job_with_teammate(db_session, profile_count=1):
    """A creator and a teammate in one organization, plus a job the creator
    owns whose interview list the creator filled."""
    from app.modules.employer.enums import OrganizationRole
    from tests.conftest import make_organization_for

    creator = make_employer()
    db_session.add(creator)
    await db_session.flush()
    organization = await make_organization_for(db_session, creator)

    teammate = make_employer()
    teammate.organization_id = organization.id
    teammate.organization_role = OrganizationRole.MEMBER.value
    db_session.add(teammate)
    await db_session.flush()

    job = make_job(creator.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    profiles = []
    for i in range(profile_count):
        profile = await make_talent_pool_profile(
            db_session,
            added_by_id=creator.id,
            override_email=f"candidate{i}@example.com",
        )
        await make_interview_list_entry(db_session, creator.id, profile.id, job.id)
        profiles.append(profile)
    return creator, teammate, job, profiles


@pytest.mark.asyncio
async def test_a_teammate_can_send_an_invite_for_a_colleagues_job(
    db_session, monkeypatch
):
    mock_email_task = _patch_invite_email(monkeypatch)
    _, teammate, job, (profile,) = await _job_with_teammate(db_session)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(teammate, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True
    mock_email_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_bulk_send_by_a_teammate_covers_candidates_the_creator_added(
    db_session, monkeypatch
):
    mock_email_task = _patch_invite_email(monkeypatch)
    _, teammate, job, _profiles = await _job_with_teammate(db_session, profile_count=2)

    service = InterviewService(db_session)
    try:
        result = await service.send_invites_to_all(teammate, job.id)
    finally:
        await service.close()

    assert result["sent"] == 2
    assert mock_email_task.delay.call_count == 2


@pytest.mark.asyncio
async def test_a_teammate_can_open_a_colleagues_interview_detail(db_session):
    _, teammate, job, (profile,) = await _job_with_teammate(db_session)
    await make_interview(
        db_session,
        job.id,
        profile.id,
        status=InterviewStatus.SCORED.value,
        transcript="Candidate: hello",
    )

    service = InterviewService(db_session)
    try:
        detail = await service.get_detail_for_employer(teammate, job.id, profile.id)
    finally:
        await service.close()

    assert detail.transcript == "Candidate: hello"


@pytest.mark.asyncio
async def test_someone_from_another_organization_is_refused_everywhere(
    db_session, monkeypatch
):
    from tests.conftest import make_organization_for

    mock_email_task = _patch_invite_email(monkeypatch)
    _, _, job, (profile,) = await _job_with_teammate(db_session)
    await make_interview(
        db_session, job.id, profile.id, status=InterviewStatus.SCORED.value
    )
    outsider = make_employer()
    db_session.add(outsider)
    await db_session.flush()
    await make_organization_for(db_session, outsider)

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service.send_invite(outsider, job.id, profile.id)
        with pytest.raises(PermissionDeniedException):
            await service.send_invites_to_all(outsider, job.id)
        with pytest.raises(PermissionDeniedException):
            await service.get_detail_for_employer(outsider, job.id, profile.id)
    finally:
        await service.close()

    mock_email_task.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Scoring an interview that finished without a score (e.g. taken on Starter)
# ---------------------------------------------------------------------------


async def _unscored_interview(db_session, plan_code="professional", **interview_fields):
    """An organization on `plan_code` (None = no subscription = Starter) with a
    finished interview that has a transcript but no AI score."""
    from tests.conftest import make_organization_for, make_subscription_for

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    if plan_code:
        await make_subscription_for(db_session, organization, plan_code=plan_code)
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    fields = {
        "status": InterviewStatus.SCORED.value,
        "transcript": "AI: Hi\n\nCandidate: Hello",
    }
    fields.update(interview_fields)
    interview = await make_interview(db_session, job.id, profile.id, **fields)
    return employer, job, profile, interview


@pytest.mark.asyncio
async def test_request_scoring_queues_an_unscored_interview(db_session, monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    employer, job, profile, interview = await _unscored_interview(db_session)

    service = InterviewService(db_session)
    try:
        result = await service.request_scoring(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result == {"queued": True}
    # Back to the state the scoring task picks up, and told not to notify again.
    assert interview.status == InterviewStatus.UPLOADED.value
    mock_task.delay.assert_called_once_with(str(interview.id), notify=False)


@pytest.mark.asyncio
async def test_request_scoring_on_the_starter_plan_asks_for_an_upgrade(
    db_session, monkeypatch
):
    from app.core.exceptions import PlanUpgradeRequiredException

    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    employer, job, profile, interview = await _unscored_interview(
        db_session, plan_code=None
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(PlanUpgradeRequiredException):
            await service.request_scoring(employer, job.id, profile.id)
    finally:
        await service.close()

    mock_task.delay.assert_not_called()
    assert interview.status == InterviewStatus.SCORED.value


@pytest.mark.asyncio
async def test_request_scoring_works_for_an_admin_owned_job(db_session, monkeypatch):
    """Admins have no organization and so no plan; they are never gated."""
    from tests.conftest import make_admin

    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    job = make_job(admin.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, added_by_id=admin.id)
    await make_interview(
        db_session,
        job.id,
        profile.id,
        status=InterviewStatus.SCORED.value,
        transcript="AI: Hi\n\nCandidate: Hello",
    )

    service = InterviewService(db_session)
    try:
        result = await service.request_scoring(admin, job.id, profile.id)
    finally:
        await service.close()

    assert result == {"queued": True}
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fields, code",
    [
        ({"ai_score": 80}, "INTERVIEW_ALREADY_SCORED"),
        ({"status": InterviewStatus.IN_PROGRESS.value}, "INTERVIEW_NOT_COMPLETED"),
        ({"status": InterviewStatus.FAILED.value}, "INTERVIEW_NOT_COMPLETED"),
        ({"status": InterviewStatus.UPLOADED.value}, "INTERVIEW_PROCESSING"),
        ({"transcript": None}, "INTERVIEW_NO_TRANSCRIPT"),
    ],
)
async def test_request_scoring_refuses_an_interview_that_cannot_be_scored(
    db_session, monkeypatch, fields, code
):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    employer, job, profile, _ = await _unscored_interview(db_session, **fields)

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException) as exc_info:
            await service.request_scoring(employer, job.id, profile.id)
    finally:
        await service.close()

    assert exc_info.value.code == code
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_a_second_click_does_not_queue_scoring_twice(db_session, monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    employer, job, profile, _ = await _unscored_interview(db_session)

    service = InterviewService(db_session)
    try:
        await service.request_scoring(employer, job.id, profile.id)
        with pytest.raises(ValidationException) as exc_info:
            await service.request_scoring(employer, job.id, profile.id)
    finally:
        await service.close()

    assert exc_info.value.code == "INTERVIEW_PROCESSING"
    assert mock_task.delay.call_count == 1


@pytest.mark.asyncio
async def test_request_scoring_retries_an_interview_stuck_processing(
    db_session, monkeypatch
):
    """If a worker died mid-run the interview sits in UPLOADED for ever; after a
    while it may be queued again instead of staying stuck."""
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    employer, job, profile, _ = await _unscored_interview(
        db_session,
        status=InterviewStatus.UPLOADED.value,
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )

    service = InterviewService(db_session)
    try:
        result = await service.request_scoring(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result == {"queued": True}
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_request_scoring_is_refused_for_someone_elses_job(db_session, monkeypatch):
    from tests.conftest import make_organization_for

    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    mock_task = _patch_scoring_task(monkeypatch)
    _, job, profile, _ = await _unscored_interview(db_session)
    outsider = make_employer()
    db_session.add(outsider)
    await db_session.flush()
    await make_organization_for(db_session, outsider)

    service = InterviewService(db_session)
    try:
        with pytest.raises(PermissionDeniedException):
            await service.request_scoring(outsider, job.id, profile.id)
    finally:
        await service.close()

    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_request_scoring_for_an_unknown_interview(db_session, monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    employer, job, _, _ = await _unscored_interview(db_session)

    service = InterviewService(db_session)
    try:
        with pytest.raises(InterviewNotFound):
            await service.request_scoring(employer, job.id, uuid4())
    finally:
        await service.close()


# ---------------------------------------------------------------------------
# Off switch and daily invite limit
# ---------------------------------------------------------------------------


def _patch_invite_email(monkeypatch):
    from unittest.mock import Mock

    from app.modules.interviews import service as interview_service_module

    mock_email_task = Mock()
    mock_email_task.delay = Mock()
    monkeypatch.setattr(
        interview_service_module, "send_ai_interview_invite_email", mock_email_task
    )
    return mock_email_task


async def _employer_job_and_profiles(db_session, profile_count=1):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    profiles = [
        await make_talent_pool_profile(
            db_session,
            added_by_id=employer.id,
            override_email=f"candidate{i}@example.com",
        )
        for i in range(profile_count)
    ]
    return employer, job, profiles


@pytest.mark.asyncio
async def test_off_switch_blocks_new_invites(db_session, monkeypatch):
    mock_email_task = _patch_invite_email(monkeypatch)
    monkeypatch.setattr(settings, "interview_enabled", False)
    employer, job, (profile,) = await _employer_job_and_profiles(db_session)

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException) as exc_info:
            await service.send_invite(employer, job.id, profile.id)
        with pytest.raises(ValidationException):
            await service.send_invites_to_all(employer, job.id)
    finally:
        await service.close()

    assert exc_info.value.code == "AI_INTERVIEWS_DISABLED"
    assert exc_info.value.status_code == 503
    mock_email_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_off_switch_blocks_starting_a_live_session(db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_enabled", False)
    _, job, (profile,) = await _employer_job_and_profiles(db_session)
    interview = await make_interview(
        db_session, job.id, profile.id, status=InterviewStatus.PENDING.value
    )

    service = InterviewService(db_session)
    try:
        with pytest.raises(ValidationException) as exc_info:
            await service._start_session(interview)
    finally:
        await service.close()

    assert exc_info.value.code == "AI_INTERVIEWS_DISABLED"
    assert interview.session_start_count == 0


@pytest.mark.asyncio
async def test_off_switch_does_not_cut_off_an_interview_already_in_progress(
    db_session, monkeypatch
):
    """Flipping the switch must not lose a candidate who is mid-interview."""
    monkeypatch.setattr(settings, "interview_enabled", False)
    mock_task = _patch_scoring_task(monkeypatch)
    _patch_recording_size(monkeypatch, size=1024)
    interview = await _make_interview_in_status(
        db_session, InterviewStatus.IN_PROGRESS.value
    )

    service = InterviewService(db_session)
    try:
        result = await service._complete_upload(interview, transcript="AI: Hi")
    finally:
        await service.close()

    assert result.status == InterviewStatus.UPLOADED.value
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_daily_invite_limit_stops_new_invites_but_not_resends(
    db_session, monkeypatch
):
    mock_email_task = _patch_invite_email(monkeypatch)
    monkeypatch.setattr(settings, "interview_daily_invite_limit", 2)
    employer, job, profiles = await _employer_job_and_profiles(
        db_session, profile_count=3
    )

    service = InterviewService(db_session)
    try:
        first = await service.send_invite(employer, job.id, profiles[0].id)
        second = await service.send_invite(employer, job.id, profiles[1].id)
        third = await service.send_invite(employer, job.id, profiles[2].id)
        resend = await service.send_invite(employer, job.id, profiles[0].id)
    finally:
        await service.close()

    assert first["sent"] is True
    assert second["sent"] is True
    assert third["sent"] is False
    assert "limit" in third["reason"].lower()
    assert resend["sent"] is True  # a resend is not a new interview
    assert mock_email_task.delay.call_count == 3

    third_row = await InterviewRepository(db_session).get_by_job_and_profile(
        job.id, profiles[2].id
    )
    assert third_row is None


@pytest.mark.asyncio
async def test_daily_invite_limit_bulk_send_sends_up_to_the_limit(
    db_session, monkeypatch
):
    _patch_invite_email(monkeypatch)
    monkeypatch.setattr(settings, "interview_daily_invite_limit", 2)
    employer, job, profiles = await _employer_job_and_profiles(
        db_session, profile_count=3
    )
    for profile in profiles:
        await make_interview_list_entry(db_session, employer.id, profile.id, job.id)

    service = InterviewService(db_session)
    try:
        result = await service.send_invites_to_all(employer, job.id)
    finally:
        await service.close()

    assert result["sent"] == 2
    assert len(result["skipped"]) == 1
    assert "limit" in result["skipped"][0]["reason"].lower()


@pytest.mark.asyncio
async def test_daily_invite_limit_ignores_old_interviews_and_other_organizations(
    db_session, monkeypatch
):
    _patch_invite_email(monkeypatch)
    monkeypatch.setattr(settings, "interview_daily_invite_limit", 1)
    employer, job, (profile,) = await _employer_job_and_profiles(db_session)

    # An old interview for this employer, and a fresh one for someone else.
    old_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview(
        db_session,
        job.id,
        old_profile.id,
        created_at=datetime.now(UTC) - timedelta(days=2),
    )
    other_employer, other_job, (other_profile,) = await _employer_job_and_profiles(
        db_session
    )
    await make_interview(db_session, other_job.id, other_profile.id)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True


@pytest.mark.asyncio
async def test_daily_invite_limit_of_zero_means_unlimited(db_session, monkeypatch):
    _patch_invite_email(monkeypatch)
    monkeypatch.setattr(settings, "interview_daily_invite_limit", 0)
    employer, job, profiles = await _employer_job_and_profiles(
        db_session, profile_count=3
    )

    service = InterviewService(db_session)
    try:
        results = [
            await service.send_invite(employer, job.id, p.id) for p in profiles
        ]
    finally:
        await service.close()

    assert all(r["sent"] for r in results)


# ---------------------------------------------------------------------------
# Employer detail: what the transcript check changes
# ---------------------------------------------------------------------------


async def _scored_interview_with_check(db_session, check_status, server_text=None):
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
        status=InterviewStatus.SCORED.value,
        transcript="Candidate: what the browser sent",
    )
    if check_status is not None:
        await InterviewRepository(db_session).create_transcript_check(
            interview.id, check_status, match_score=0.1, server_transcript=server_text
        )
    return employer, job, tp_profile


@pytest.mark.asyncio
async def test_detail_shows_the_recordings_transcript_on_a_mismatch(db_session):
    employer, job, tp_profile = await _scored_interview_with_check(
        db_session, "MISMATCH", server_text="what the recording actually says"
    )

    service = InterviewService(db_session)
    try:
        detail = await service.get_detail_for_employer(
            employer, job.id, tp_profile.id
        )
    finally:
        await service.close()

    assert detail.transcript == "what the recording actually says"
    assert detail.transcript_check == "MISMATCH"


@pytest.mark.asyncio
@pytest.mark.parametrize("check_status", ["VERIFIED", "UNAVAILABLE", None])
async def test_detail_shows_the_submitted_transcript_otherwise(
    db_session, check_status
):
    employer, job, tp_profile = await _scored_interview_with_check(
        db_session, check_status, server_text="recording transcript"
    )

    service = InterviewService(db_session)
    try:
        detail = await service.get_detail_for_employer(
            employer, job.id, tp_profile.id
        )
    finally:
        await service.close()

    assert detail.transcript == "Candidate: what the browser sent"
    assert detail.transcript_check == check_status


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


def test_instructions_make_the_time_limit_a_ceiling_and_describe_a_clean_close():
    from app.modules.interviews.service import _build_instructions

    text = " ".join(
        _build_instructions("Ask about scaling.", 15, can_end_interview=True).split()
    )

    assert "ceiling, not a target" in text
    assert "at most two follow-ups" in text.lower()
    assert "Never invent extra questions" in text
    assert "HOW TO CLOSE" in text
    assert "call the end_interview function" in text
    assert text.endswith("Interview brief: Ask about scaling.")


def test_instructions_without_the_end_tool_never_mention_it():
    from app.modules.interviews.service import _build_instructions

    text = _build_instructions("Ask about scaling.", 15, can_end_interview=False)

    assert "end_interview" not in text
    assert "ceiling, not a target" in text  # the pacing guidance still applies
    assert "stop speaking and wait" in text


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [True, False])
async def test_start_session_offers_the_end_tool_only_when_enabled(
    db_session, monkeypatch, enabled
):
    monkeypatch.setattr(settings, "interview_ai_can_end_early", enabled)
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(db_session, job.id, tp_profile.id)

    service = InterviewService(db_session)
    service._client = _mock_realtime_client_secret()
    try:
        interview = await InterviewRepository(db_session).get_by_id(interview.id)
        await service._start_session(interview)
        session = service._client.realtime.client_secrets.create.await_args.kwargs[
            "session"
        ]
    finally:
        await service.close()

    if enabled:
        assert [t["name"] for t in session["tools"]] == ["end_interview"]
        assert session["tool_choice"] == "auto"
        assert "end_interview" in session["instructions"]
    else:
        assert "tools" not in session
        assert "end_interview" not in session["instructions"]


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
