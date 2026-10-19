"""An AI interview costs credits: taken at the first invite, not on a resend.

The organization that owns the job pays. Elevare's own admin-owned jobs, jobs
whose owner has no organization, and a price of 0 are never charged."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import InsufficientCreditsException
from app.modules.credits.models import CreditTransaction
from app.modules.credits.service import CreditsService
from app.modules.interviews import service as interview_service_module
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import Interview
from app.modules.interviews.service import InterviewService
from tests.conftest import (
    make_admin,
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)

from .conftest import (
    make_interview,
    make_interview_list_entry,
    make_talent_pool_profile,
)

BRIEF = "Probe distributor management."
EMAIL = "candidate@example.com"


@pytest.fixture(autouse=True)
def invite_email(monkeypatch):
    """Do not send email; keep the call to assert on."""
    task = Mock()
    monkeypatch.setattr(interview_service_module, "send_ai_interview_invite_email", task)
    return task


@pytest.fixture(autouse=True)
def plan_gates_on(monkeypatch):
    """With plan gates off (the local testing escape hatch) every organization
    resolves to Professional, which would hide the Starter behaviour tested here."""
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _client(db_session, balance=100, with_org=True, plan_code=None):
    """An employer (owner of the job) in an organization holding ``balance`` credits,
    on ``plan_code`` (None = no subscription = Starter)."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = None
    if with_org:
        organization = await make_organization_for(db_session, employer)
        if plan_code:
            await make_subscription_for(db_session, organization, plan_code=plan_code)
        if balance:
            await CreditsService(db_session).grant(organization.id, balance)
    job = make_job(employer.id, interview_brief=BRIEF)
    db_session.add(job)
    await db_session.flush()
    return employer, organization, job


async def _profile(db_session, owner):
    return await make_talent_pool_profile(
        db_session, added_by_id=owner.id, override_email=EMAIL
    )


async def _balance(db_session, organization):
    return await CreditsService(db_session).get_balance(organization.id)


async def _interviews(db_session, job):
    result = await db_session.execute(select(Interview).where(Interview.job_id == job.id))
    return result.scalars().all()


async def _ledger(db_session, organization):
    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.employer_id == organization.id)
    )
    return [(row.reason, row.delta, row.reference_id) for row in result.scalars().all()]


@pytest.mark.asyncio
async def test_the_first_invite_charges_the_organization_that_owns_the_job(
    db_session, invite_email
):
    employer, organization, job = await _client(db_session)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True
    assert await _balance(db_session, organization) == 90
    interview = (await _interviews(db_session, job))[0]
    charges = [row for row in await _ledger(db_session, organization) if row[0] == "interview_charge"]
    assert charges == [("interview_charge", -10, interview.id)]
    invite_email.delay.assert_called_once()


@pytest.mark.asyncio
async def test_a_resend_is_free(db_session):
    employer, organization, job = await _client(db_session)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        await service.send_invite(employer, job.id, profile.id)
        again = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert again["sent"] is True
    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_copying_the_link_after_sending_is_free_and_before_sending_charges(
    db_session,
):
    employer, organization, job = await _client(db_session)
    sent_profile = await _profile(db_session, employer)
    fresh_profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        await service.send_invite(employer, job.id, sent_profile.id)
        await service.get_interview_link(employer, job.id, sent_profile.id)
        assert await _balance(db_session, organization) == 90

        await service.get_interview_link(employer, job.id, fresh_profile.id)
    finally:
        await service.close()

    assert await _balance(db_session, organization) == 80


@pytest.mark.asyncio
async def test_not_enough_credits_refuses_the_invite_and_leaves_nothing_behind(
    db_session, invite_email
):
    employer, organization, job = await _client(db_session, balance=4)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is False
    assert "Not enough credits" in result["reason"]
    assert "10" in result["reason"]
    assert await _balance(db_session, organization) == 4
    assert await _interviews(db_session, job) == []
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_not_enough_credits_refuses_the_link_with_a_402(db_session):
    employer, organization, job = await _client(db_session, balance=0)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        with pytest.raises(InsufficientCreditsException) as raised:
            await service.get_interview_link(employer, job.id, profile.id)
    finally:
        await service.close()

    assert raised.value.status_code == 402
    assert raised.value.code == "INSUFFICIENT_CREDITS"
    assert await _interviews(db_session, job) == []


@pytest.mark.asyncio
async def test_sending_to_all_invites_as_many_as_the_balance_covers(db_session):
    employer, organization, job = await _client(db_session, balance=25)
    profiles = [await _profile(db_session, employer) for _ in range(3)]
    for profile in profiles:
        await make_interview_list_entry(db_session, employer.id, profile.id, job.id)

    service = InterviewService(db_session)
    try:
        result = await service.send_invites_to_all(employer, job.id)
    finally:
        await service.close()

    assert result["sent"] == 2
    assert len(result["skipped"]) == 1
    assert "Not enough credits" in result["skipped"][0]["reason"]
    assert len(await _interviews(db_session, job)) == 2
    assert await _balance(db_session, organization) == 5


@pytest.mark.asyncio
async def test_a_refused_invite_does_not_leave_a_half_created_interview_for_the_next_one(
    db_session,
):
    """In 'send to all', a candidate who cannot be afforded must not get an
    interview row that the next candidate's save would commit."""
    employer, organization, job = await _client(db_session, balance=10)
    first, second = await _profile(db_session, employer), await _profile(db_session, employer)
    for profile in (first, second):
        await make_interview_list_entry(db_session, employer.id, profile.id, job.id)

    service = InterviewService(db_session)
    try:
        await service.send_invites_to_all(employer, job.id)
    finally:
        await service.close()

    interviews = await _interviews(db_session, job)
    assert len(interviews) == 1
    assert await _balance(db_session, organization) == 0


@pytest.mark.asyncio
async def test_a_teammates_invite_charges_the_shared_wallet(db_session):
    from app.modules.employer.enums import OrganizationRole

    owner, organization, job = await _client(db_session)
    teammate = make_employer()
    db_session.add(teammate)
    await db_session.flush()
    teammate.organization_id = organization.id
    teammate.organization_role = OrganizationRole.MEMBER.value
    await db_session.flush()
    profile = await _profile(db_session, owner)

    service = InterviewService(db_session)
    try:
        await service.send_invite(teammate, job.id, profile.id)
    finally:
        await service.close()

    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_elevares_own_admin_owned_jobs_are_never_charged(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    job = make_job(admin.id, interview_brief=BRIEF)
    db_session.add(job)
    await db_session.flush()
    profile = await _profile(db_session, admin)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(admin, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True
    assert len(await _interviews(db_session, job)) == 1


@pytest.mark.asyncio
async def test_a_job_whose_owner_has_no_organization_is_not_charged(db_session):
    employer, _organization, job = await _client(db_session, with_org=False)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True


@pytest.mark.asyncio
async def test_a_price_of_zero_charges_nothing(db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_credit_cost", 0)
    employer, organization, job = await _client(db_session, balance=0)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True
    assert await _balance(db_session, organization) == 0


@pytest.mark.asyncio
async def test_the_price_is_read_when_the_invite_is_sent(db_session, monkeypatch):
    monkeypatch.setattr(settings, "interview_credit_cost", 25)
    employer, organization, job = await _client(db_session)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert await _balance(db_session, organization) == 75


@pytest.mark.asyncio
async def test_an_invite_refunded_after_expiry_is_charged_again_when_resent(db_session):
    employer, organization, job = await _client(db_session)
    profile = await _profile(db_session, employer)
    service = InterviewService(db_session)
    try:
        await service.send_invite(employer, job.id, profile.id)
        interview = (await _interviews(db_session, job))[0]
        # The link expires unused and the credits are given back.
        interview.token_expires_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.flush()
        await CreditsService(db_session).refund_interview(organization.id, interview.id)
        assert await _balance(db_session, organization) == 100

        await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert await _balance(db_session, organization) == 90


@pytest.mark.asyncio
async def test_a_refused_resend_leaves_the_existing_interview_untouched(db_session):
    """An interview that was never charged (for example one sent before credits
    existed) is charged on a resend; if they cannot afford it, nothing changes."""
    employer, organization, job = await _client(db_session, balance=0)
    profile = await _profile(db_session, employer)
    interview = await make_interview(
        db_session,
        job.id,
        profile.id,
        token="old-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=3),
    )

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is False
    await db_session.refresh(interview)
    assert interview.token == "old-token"


@pytest.mark.asyncio
async def test_a_lapsed_subscription_is_charged_like_starter(db_session):
    """An EXPIRED subscription no longer gives the plan, so credits apply."""
    employer, organization, job = await _client(db_session, balance=4, plan_code="professional")
    from sqlalchemy import update

    from app.modules.billing.models import Subscription

    await db_session.execute(
        update(Subscription)
        .where(Subscription.organization_id == organization.id)
        .values(status="EXPIRED")
    )
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is False
    assert "Not enough credits" in result["reason"]


@pytest.mark.asyncio
async def test_a_subscriber_pays_for_an_interview_like_anyone_else(db_session):
    """No plan makes interviews free: a Professional organization with no credits
    left is refused, and is told to buy more."""
    employer, organization, job = await _client(
        db_session, balance=0, plan_code="professional"
    )
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is False
    assert "Not enough credits" in result["reason"]


@pytest.mark.asyncio
async def test_a_subscribers_interview_comes_out_of_its_plan_credits_first(
    db_session,
):
    employer, organization, job = await _client(
        db_session, balance=5, plan_code="professional"
    )
    credits = CreditsService(db_session)
    await credits.reset_plan_allowance(organization.id, 40, uuid4())
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is True
    assert await credits.get_balances(organization.id) == {
        "total": 35,
        "plan_credits": 30,
        "purchased_credits": 5,
    }


@pytest.mark.asyncio
async def test_with_plan_gates_off_interviews_are_still_charged(db_session, monkeypatch):
    """The testing escape hatch makes every organization Professional (see
    BillingService.get_effective_plan); that no longer waives the charge."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    employer, organization, job = await _client(db_session, balance=0)
    profile = await _profile(db_session, employer)

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is False
    assert "Not enough credits" in result["reason"]


@pytest.mark.asyncio
async def test_pricing_shows_a_subscriber_both_pots(db_session):
    employer, organization, _job = await _client(
        db_session, balance=7, plan_code="professional"
    )
    await CreditsService(db_session).reset_plan_allowance(organization.id, 40, uuid4())

    service = InterviewService(db_session)
    try:
        pricing = await service.get_pricing(employer)
    finally:
        await service.close()

    assert pricing == {
        "credits_per_interview": 10,
        "balance": 47,
        "charged": True,
        "included_in_plan": False,
        "plan_credits": 40,
        "purchased_credits": 7,
    }


@pytest.mark.asyncio
async def test_pricing_tells_an_employer_the_cost_and_their_balance(db_session):
    employer, _organization, _job = await _client(db_session, balance=42)

    service = InterviewService(db_session)
    try:
        pricing = await service.get_pricing(employer)
    finally:
        await service.close()

    assert pricing == {
        "credits_per_interview": 10,
        "balance": 42,
        "charged": True,
        "included_in_plan": False,
        "plan_credits": 0,
        "purchased_credits": 42,
    }


@pytest.mark.asyncio
async def test_pricing_says_an_admin_is_not_charged(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()

    service = InterviewService(db_session)
    try:
        pricing = await service.get_pricing(admin)
    finally:
        await service.close()

    assert pricing["charged"] is False
    assert pricing["balance"] is None


@pytest.mark.asyncio
async def test_pricing_says_nothing_is_charged_when_the_price_is_zero(
    db_session, monkeypatch
):
    monkeypatch.setattr(settings, "interview_credit_cost", 0)
    employer, _organization, _job = await _client(db_session, balance=42)

    service = InterviewService(db_session)
    try:
        pricing = await service.get_pricing(employer)
    finally:
        await service.close()

    assert pricing["charged"] is False


@pytest.mark.asyncio
async def test_pricing_for_an_owner_with_no_organization_is_not_charged(db_session):
    employer, _organization, _job = await _client(db_session, with_org=False)

    service = InterviewService(db_session)
    try:
        pricing = await service.get_pricing(employer)
    finally:
        await service.close()

    assert pricing["charged"] is False


@pytest.mark.asyncio
async def test_a_finished_interview_is_not_charged_again(db_session):
    employer, organization, job = await _client(db_session)
    profile = await _profile(db_session, employer)
    await make_interview(
        db_session,
        job.id,
        profile.id,
        status=InterviewStatus.SCORED.value,
        token="done",
        token_expires_at=datetime.now(UTC) + timedelta(days=3),
    )

    service = InterviewService(db_session)
    try:
        result = await service.send_invite(employer, job.id, profile.id)
    finally:
        await service.close()

    assert result["sent"] is False
    assert await _balance(db_session, organization) == 100
