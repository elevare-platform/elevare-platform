"""The Starter plan's job rules: the taste job, the applicant limits, and one new job a month."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import JobPostingLimitExceededException
from app.modules.ai import tasks as ai_tasks
from app.modules.billing.allowance import AllowanceService, month_window
from app.modules.billing.models import PlanGateExemption
from app.modules.billing.service import BillingService
from app.modules.billing.starter_rules import (
    LATER_APPLICANT_LIMIT,
    TASTE_APPLICANT_LIMIT,
    applicant_limit,
    claim_taste_if_first,
    is_taste_job,
)
from app.modules.jobs.enums import JobStatus
from app.modules.jobs.service import JobService
from app.modules.talent_pool.service import TalentPoolService
from tests.conftest import (
    make_admin,
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    # A publish queues background scoring of the pool; it is not what is tested here.
    monkeypatch.setattr(ai_tasks.score_job_against_talent_pool_task, "delay", MagicMock())


async def _company(db_session, kyc="APPROVED", plan=None, exempt=False):
    """An employer with a company (verified by default). Returns (owner, organization)."""
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(
        db_session, owner, company_name="Acme", is_profile_complete=True, kyc_status=kyc
    )
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    if exempt:
        db_session.add(PlanGateExemption(organization_id=organization.id, reason="Pilot"))
        await db_session.flush()
    return owner, organization


async def _job(db_session, owner, **overrides):
    """A job. A DRAFT unless told otherwise, like a job waiting to be published."""
    overrides.setdefault("status", JobStatus.DRAFT.value)
    job = make_job(owner.id, **overrides)
    db_session.add(job)
    await db_session.flush()
    return job


def _days_ago(days):
    return datetime.now(UTC) - timedelta(days=days)


# --- the taste job -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_first_job_published_becomes_the_taste_job_and_later_ones_do_not(db_session):
    owner, organization = await _company(db_session)
    first = await _job(db_session, owner)
    second = await _job(db_session, owner, title="Second")

    await claim_taste_if_first(db_session, organization.id, first.id)
    await claim_taste_if_first(db_session, organization.id, second.id)
    await db_session.flush()  # the caller commits; flushing stands in for that here

    await db_session.refresh(organization)
    assert organization.taste_job_id == first.id


@pytest.mark.asyncio
async def test_a_company_with_no_record_claims_nothing(db_session):
    await claim_taste_if_first(db_session, None, uuid.uuid4())  # no error


@pytest.mark.asyncio
async def test_the_taste_only_works_for_a_verified_company(db_session):
    owner, organization = await _company(db_session, kyc="PENDING")
    job = await _job(db_session, owner)
    organization.taste_job_id = job.id
    await db_session.flush()

    assert await is_taste_job(db_session, organization.id, job.id) is False

    organization.kyc_status = "APPROVED"  # verified later: the taste starts then
    await db_session.flush()

    assert await is_taste_job(db_session, organization.id, job.id) is True
    assert await is_taste_job(db_session, organization.id, uuid.uuid4()) is False


# --- applicant limits ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_taste_job_takes_ten_applicants_and_later_starter_jobs_take_three(db_session):
    owner, organization = await _company(db_session)
    taste = await _job(db_session, owner)
    later = await _job(db_session, owner, title="Later")
    organization.taste_job_id = taste.id
    await db_session.flush()

    assert await applicant_limit(db_session, taste) == TASTE_APPLICANT_LIMIT == 10
    assert await applicant_limit(db_session, later) == LATER_APPLICANT_LIMIT == 3


@pytest.mark.asyncio
async def test_an_unverified_company_gets_the_smaller_limit_even_on_its_first_job(db_session):
    owner, organization = await _company(db_session, kyc="NOT_SUBMITTED")
    job = await _job(db_session, owner)
    organization.taste_job_id = job.id
    await db_session.flush()

    assert await applicant_limit(db_session, job) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["professional", "exempt"])
async def test_professional_access_means_no_applicant_limit(db_session, how):
    owner, _organization = await _company(
        db_session, plan="professional" if how == "professional" else None, exempt=how == "exempt"
    )
    job = await _job(db_session, owner)

    assert await applicant_limit(db_session, job) is None


@pytest.mark.asyncio
async def test_an_admins_job_and_a_job_with_no_company_have_no_limit(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    admin_job = await _job(db_session, admin)
    owner = make_employer()  # an employer with no company record
    db_session.add(owner)
    await db_session.flush()
    orphan_job = await _job(db_session, owner)

    assert await applicant_limit(db_session, admin_job) is None
    assert await applicant_limit(db_session, orphan_job) is None


@pytest.mark.asyncio
async def test_no_applicant_limit_while_plan_gating_is_off(db_session, monkeypatch):
    """Production today: gating is off, so a Starter job takes any number of applicants."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    owner, _organization = await _company(db_session)
    job = await _job(db_session, owner)

    assert await applicant_limit(db_session, job) is None


# --- one new job a month -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_starter_company_that_published_this_month_cannot_publish_another(db_session):
    owner, organization = await _company(db_session)
    await _job(db_session, owner, status=JobStatus.CLOSED.value, published_at=_days_ago(0))
    waiting = await _job(db_session, owner, title="Waiting")

    with pytest.raises(JobPostingLimitExceededException) as refused:
        await BillingService(db_session).assert_can_post_job(organization.id, job_id=waiting.id)

    _start, next_start = month_window()
    assert "one new job a month" in refused.value.message
    assert "from 1" in refused.value.message  # says when it can be published


@pytest.mark.asyncio
async def test_a_job_published_last_month_does_not_use_this_months_slot(db_session):
    owner, organization = await _company(db_session)
    start, _ = month_window()
    await _job(
        db_session,
        owner,
        status=JobStatus.CLOSED.value,
        published_at=start - timedelta(days=3),
    )
    waiting = await _job(db_session, owner, title="Waiting")

    await BillingService(db_session).assert_can_post_job(organization.id, job_id=waiting.id)


@pytest.mark.asyncio
async def test_the_job_being_published_is_not_counted_against_itself(db_session):
    owner, organization = await _company(db_session)
    job = await _job(db_session, owner, published_at=_days_ago(0), status=JobStatus.DRAFT.value)

    await BillingService(db_session).assert_can_post_job(organization.id, job_id=job.id)


@pytest.mark.asyncio
async def test_a_professional_company_may_publish_more_than_one_a_month(db_session):
    owner, organization = await _company(db_session, plan="professional")
    await _job(db_session, owner, status=JobStatus.CLOSED.value, published_at=_days_ago(0))
    waiting = await _job(db_session, owner, title="Waiting")

    await BillingService(db_session).assert_can_post_job(organization.id, job_id=waiting.id)


# --- publishing, end to end ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_publishing_stamps_the_date_claims_the_taste_and_clears_a_disabled_state(db_session):
    owner, organization = await _company(db_session)
    job = await _job(
        db_session,
        owner,
        status=JobStatus.DRAFT.value,
        moderation_status="APPROVED",
        disabled_reason="EXPIRED",
        disabled_at=_days_ago(40),
    )

    published = await JobService(db_session).publish_job(job.id, owner)

    assert published.status == "ACTIVE"
    await db_session.refresh(job)
    assert job.published_at is not None
    assert (datetime.now(UTC) - job.published_at) < timedelta(minutes=1)
    assert job.disabled_reason is None and job.disabled_at is None
    await db_session.refresh(organization)
    assert organization.taste_job_id == job.id


@pytest.mark.asyncio
async def test_a_second_publish_does_not_take_the_taste_from_the_first_job(db_session):
    owner, organization = await _company(db_session, plan="professional")
    first = await _job(db_session, owner, status=JobStatus.CLOSED.value, published_at=_days_ago(40))
    organization.taste_job_id = first.id
    second = await _job(
        db_session, owner, title="Second", status=JobStatus.DRAFT.value, moderation_status="APPROVED"
    )

    await JobService(db_session).publish_job(second.id, owner)

    await db_session.refresh(organization)
    assert organization.taste_job_id == first.id


# --- scoring the taste ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_starter_may_score_candidates_on_its_taste_job_and_nowhere_else(db_session):
    owner, organization = await _company(db_session)
    taste = await _job(db_session, owner)
    later = await _job(db_session, owner, title="Later")
    organization.taste_job_id = taste.id
    await db_session.flush()
    allowance = AllowanceService(db_session)

    assert await allowance.may_score(organization.id, taste.id, application_id=uuid.uuid4())
    assert not await allowance.may_score(organization.id, later.id, application_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_the_taste_does_not_let_a_professional_company_past_its_allowance(db_session):
    """The taste is Starter's. A Professional company that has spent its allowance is still
    stopped on its first job."""
    from sqlalchemy import select

    from app.modules.ai.models import FitScoringCost
    from app.modules.billing.models import Plan
    from tests.interviews.conftest import make_talent_pool_profile

    owner, organization = await _company(db_session, plan="professional")
    taste = await _job(db_session, owner)
    organization.taste_job_id = taste.id
    plan = (await db_session.execute(select(Plan).where(Plan.code == "professional"))).scalar_one()
    plan.monthly_ai_scores = 1
    other = await make_talent_pool_profile(db_session, owner.id)
    db_session.add(
        FitScoringCost(
            job_id=taste.id,
            talent_pool_profile_id=other.id,
            input_tokens=1,
            output_tokens=1,
            model="m",
        )
    )  # the one score of the month is used
    await db_session.flush()

    allowed = await AllowanceService(db_session).may_score(
        organization.id, taste.id, application_id=uuid.uuid4()
    )

    assert allowed is False


@pytest.mark.asyncio
async def test_a_plan_with_a_limit_of_zero_is_not_starter_and_gets_no_taste(db_session):
    """Starter is recognised by its plan, not by having a limit of 0."""
    from sqlalchemy import select

    from app.modules.billing.models import Plan

    owner, organization = await _company(db_session, plan="professional")
    taste = await _job(db_session, owner)
    organization.taste_job_id = taste.id
    plan = (await db_session.execute(select(Plan).where(Plan.code == "professional"))).scalar_one()
    plan.monthly_ai_scores = 0
    await db_session.flush()

    allowed = await AllowanceService(db_session).may_score(
        organization.id, taste.id, application_id=uuid.uuid4()
    )

    assert allowed is False


@pytest.mark.asyncio
async def test_uploads_attached_to_the_taste_job_are_scored_on_starter(db_session):
    owner, organization = await _company(db_session)
    taste = await _job(db_session, owner)
    later = await _job(db_session, owner, title="Later")
    organization.taste_job_id = taste.id
    await db_session.flush()
    pool = TalentPoolService(db_session, cv_service=None)

    assert await pool._can_auto_score(owner, taste.id) is True
    assert await pool._can_auto_score(owner, later.id) is False
    assert await pool._can_auto_score(owner, None) is False


@pytest.mark.asyncio
async def test_a_professional_company_always_auto_scores_uploads(db_session):
    owner, _organization = await _company(db_session, plan="professional")
    pool = TalentPoolService(db_session, cv_service=None)

    assert await pool._can_auto_score(owner, None) is True

