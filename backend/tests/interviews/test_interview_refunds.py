"""Credits come back when an interview was not delivered.

Refunded: an invite that expired without the candidate opening it (an hourly
sweep), and an interview whose pipeline failed for good (immediately). Not
refunded: a candidate who started and abandoned the interview (the realtime cost
was spent, and a resend is free), and a finished interview."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from sqlalchemy import event, select

from app.modules.credits.models import CreditTransaction
from app.modules.credits.service import CreditsService
from app.modules.interviews import service as interview_service_module
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.credits import refund_if_unused
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from tests.conftest import make_admin, make_employer, make_job, make_organization_for

from .conftest import make_interview, make_talent_pool_profile
from .test_interview_tasks import _patch_engine_to_use_test_session

PRICE = 10


async def _paid_interview(
    db_session,
    *,
    expired=True,
    session_start_count=0,
    status=InterviewStatus.PENDING.value,
    charged=True,
    admin_owned=False,
    employer=None,
    organization=None,
    **fields,
):
    """An interview whose invite is (by default) expired and unopened, charged to
    an organization that started with 100 credits."""
    if employer is None:
        employer = make_admin() if admin_owned else make_employer()
        db_session.add(employer)
        await db_session.flush()
        if not admin_owned:
            organization = await make_organization_for(db_session, employer)
            await CreditsService(db_session).grant(organization.id, 100)
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    expiry = datetime.now(UTC) + timedelta(days=-1 if expired else 3)
    interview = await make_interview(
        db_session,
        job.id,
        profile.id,
        status=status,
        token=f"token-{job.id}",
        token_expires_at=expiry,
        session_start_count=session_start_count,
        **fields,
    )
    if charged and organization is not None:
        await CreditsService(db_session).charge_interview(
            organization.id, interview.id, PRICE
        )
    await db_session.commit()
    return employer, organization, interview


async def _balance(db_session, organization):
    return await CreditsService(db_session).get_balance(organization.id)


async def _refund_rows(db_session, interview):
    result = await db_session.execute(
        select(CreditTransaction).where(
            CreditTransaction.reference_id == interview.id,
            CreditTransaction.reason == "interview_refund",
        )
    )
    return result.scalars().all()


async def _sweep(db_session, monkeypatch, **kwargs):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    return await interviews_tasks._refund_unused_interviews_async(**kwargs)


# ── The hourly sweep: an invite that expired unopened ───────────────────────────


@pytest.mark.asyncio
async def test_an_expired_unopened_invite_is_refunded(db_session, monkeypatch):
    _, organization, interview = await _paid_interview(db_session)
    assert await _balance(db_session, organization) == 90

    refunded = await _sweep(db_session, monkeypatch)

    assert refunded == 1
    assert await _balance(db_session, organization) == 100
    assert len(await _refund_rows(db_session, interview)) == 1


@pytest.mark.asyncio
async def test_running_the_sweep_again_refunds_nothing_more(db_session, monkeypatch):
    _, organization, interview = await _paid_interview(db_session)

    await _sweep(db_session, monkeypatch)
    again = await _sweep(db_session, monkeypatch)

    assert again == 0
    assert await _balance(db_session, organization) == 100
    assert len(await _refund_rows(db_session, interview)) == 1


@pytest.mark.asyncio
async def test_an_invite_that_has_not_expired_is_left_alone(db_session, monkeypatch):
    _, organization, _ = await _paid_interview(db_session, expired=False)

    assert await _sweep(db_session, monkeypatch) == 0
    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_an_interview_the_candidate_started_is_not_refunded(
    db_session, monkeypatch
):
    """The realtime session may already have cost money."""
    _, organization, _ = await _paid_interview(db_session, session_start_count=1)

    assert await _sweep(db_session, monkeypatch) == 0
    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_an_abandoned_interview_marked_failed_is_not_refunded(
    db_session, monkeypatch
):
    _, organization, _ = await _paid_interview(
        db_session, status=InterviewStatus.FAILED.value, session_start_count=1
    )

    assert await _sweep(db_session, monkeypatch) == 0
    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status", [InterviewStatus.UPLOADED.value, InterviewStatus.SCORED.value]
)
async def test_a_finished_interview_is_not_refunded(db_session, monkeypatch, status):
    _, organization, _ = await _paid_interview(db_session, status=status)

    assert await _sweep(db_session, monkeypatch) == 0
    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_an_interview_that_was_never_charged_is_left_alone(db_session, monkeypatch):
    """One sent before credits existed: there is nothing to give back."""
    _, organization, _ = await _paid_interview(db_session, charged=False)

    assert await _sweep(db_session, monkeypatch) == 0
    assert await _balance(db_session, organization) == 100


@pytest.mark.asyncio
async def test_a_backlog_is_worked_through_in_batches_without_getting_stuck(
    db_session, monkeypatch
):
    """Refunded interviews stay 'pending' forever; they must not crowd out the
    ones still waiting."""
    employer, organization, _first = await _paid_interview(db_session)
    for _ in range(2):
        await _paid_interview(
            db_session, employer=employer, organization=organization
        )
    assert await _balance(db_session, organization) == 70

    assert await _sweep(db_session, monkeypatch, limit=2) == 2
    assert await _sweep(db_session, monkeypatch, limit=2) == 1
    assert await _sweep(db_session, monkeypatch, limit=2) == 0
    assert await _balance(db_session, organization) == 100


@pytest.mark.asyncio
async def test_a_resend_that_lands_before_the_refund_prevents_it(db_session):
    """The sweep re-checks under the interview's lock: an invite resent in the
    meantime is valid again and must keep its charge."""
    _, organization, interview = await _paid_interview(db_session)
    interview.token_expires_at = datetime.now(UTC) + timedelta(days=14)  # resent
    await db_session.flush()

    refunded = await refund_if_unused(db_session, interview.id, datetime.now(UTC))

    assert refunded == 0
    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_a_resend_locks_the_interview_before_deciding_to_charge(db_session):
    """The other half of the race: a resend and the sweep must take turns."""
    employer, organization, interview = await _paid_interview(db_session)
    job = await interview_job(db_session, interview)

    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    connection = (await db_session.connection()).sync_connection
    event.listen(connection, "before_cursor_execute", capture)
    try:
        service = InterviewService(db_session)
        try:
            await service.create_invite(job, interview.talent_pool_profile_id)
        finally:
            await service.close()
    finally:
        event.remove(connection, "before_cursor_execute", capture)

    assert any(
        "FROM interviews" in s and "FOR UPDATE" in s for s in statements
    ), "a resend must lock the interview row"


async def interview_job(db_session, interview):
    from app.modules.jobs.repository import JobRepository

    return await JobRepository(db_session).get_by_id(interview.job_id)


@pytest.mark.asyncio
async def test_a_refunded_invite_that_is_resent_is_charged_again(db_session, monkeypatch):
    monkeypatch.setattr(
        interview_service_module, "send_ai_interview_invite_email", Mock()
    )
    _, organization, interview = await _paid_interview(db_session)
    await _sweep(db_session, monkeypatch)
    assert await _balance(db_session, organization) == 100

    job = await interview_job(db_session, interview)
    service = InterviewService(db_session)
    try:
        await service.create_invite(job, interview.talent_pool_profile_id)
    finally:
        await service.close()

    assert await _balance(db_session, organization) == 90


# ── A pipeline failure for good ────────────────────────────────────────────────


def _failing_scorer(monkeypatch):
    instance = MagicMock()
    instance.score_interview_transcript = AsyncMock(
        side_effect=RuntimeError("simulated failure")
    )
    instance._client.close = AsyncMock()
    monkeypatch.setattr(
        interviews_tasks, "AnthropicCVExtractionService", Mock(return_value=instance)
    )


async def _uploaded_paid_interview(db_session, **kwargs):
    return await _paid_interview(
        db_session,
        expired=False,
        status=InterviewStatus.UPLOADED.value,
        session_start_count=1,
        r2_key="interviews/test/recording.webm",
        transcript="AI: Hi\n\nCandidate: Hello",
        **kwargs,
    )


@pytest.mark.asyncio
async def test_a_pipeline_failure_for_good_refunds_the_interview(db_session, monkeypatch):
    monkeypatch.setattr(interviews_tasks.settings, "plan_gates_enabled", False)
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, organization, interview = await _uploaded_paid_interview(db_session)
    _failing_scorer(monkeypatch)

    with pytest.raises(RuntimeError):
        await interviews_tasks._transcribe_and_score_interview_async(
            str(interview.id), mark_failed_on_error=True
        )

    updated = await InterviewRepository(db_session).get_by_id(interview.id)
    assert updated.status == InterviewStatus.FAILED.value
    assert await _balance(db_session, organization) == 100
    assert len(await _refund_rows(db_session, interview)) == 1


@pytest.mark.asyncio
async def test_a_failed_attempt_that_will_be_retried_does_not_refund(
    db_session, monkeypatch
):
    monkeypatch.setattr(interviews_tasks.settings, "plan_gates_enabled", False)
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, organization, interview = await _uploaded_paid_interview(db_session)
    _failing_scorer(monkeypatch)

    with pytest.raises(RuntimeError):
        await interviews_tasks._transcribe_and_score_interview_async(
            str(interview.id), mark_failed_on_error=False
        )

    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_a_failure_on_an_admin_owned_job_has_nothing_to_refund(
    db_session, monkeypatch
):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    _, _, interview = await _uploaded_paid_interview(db_session, admin_owned=True)
    _failing_scorer(monkeypatch)

    with pytest.raises(RuntimeError):
        await interviews_tasks._transcribe_and_score_interview_async(
            str(interview.id), mark_failed_on_error=True
        )

    updated = await InterviewRepository(db_session).get_by_id(interview.id)
    assert updated.status == InterviewStatus.FAILED.value
    assert await _refund_rows(db_session, interview) == []
