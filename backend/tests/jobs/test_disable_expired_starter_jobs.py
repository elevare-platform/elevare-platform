"""A Starter job is switched off after 30 days, the other half of "10 applicants or 30 days,
whichever comes first". Professional companies, exempt companies, admins and anything that is
not live are left alone, and nothing happens while plan gating is off."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.modules.billing.models import PlanGateExemption
from app.modules.jobs.disabling import disable_expired_starter_jobs
from app.modules.jobs.enums import JobStatus
from app.modules.notifications.models import Notification
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


def _days_ago(days):
    return datetime.now(UTC) - timedelta(days=days)


async def _company(db_session, plan=None, exempt=False):
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(db_session, owner, company_name="Acme")
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    if exempt:
        db_session.add(PlanGateExemption(organization_id=organization.id, reason="Pilot"))
        await db_session.flush()
    return owner


async def _live_job(db_session, owner, days, status=JobStatus.ACTIVE.value):
    job = make_job(owner.id, status=status, published_at=_days_ago(days))
    db_session.add(job)
    await db_session.flush()
    return job


async def _state(db_session, job):
    await db_session.refresh(job)
    return job.status, job.disabled_reason


@pytest.mark.asyncio
async def test_a_starter_job_past_thirty_days_is_switched_off_and_the_employer_told(db_session):
    owner = await _company(db_session)
    job = await _live_job(db_session, owner, days=31)

    switched_off = await disable_expired_starter_jobs(db_session)

    assert switched_off >= 1
    assert await _state(db_session, job) == ("DISABLED", "EXPIRED")
    notification = (
        await db_session.execute(
            select(Notification).where(
                Notification.recipient_id == owner.id, Notification.type == "JOB_DISABLED"
            )
        )
    ).scalar_one()
    assert "has ended" in notification.title
    assert "30 days" in notification.body
    assert "re-publish" in notification.body


@pytest.mark.asyncio
async def test_a_starter_job_inside_thirty_days_is_left_running(db_session):
    owner = await _company(db_session)
    job = await _live_job(db_session, owner, days=29)

    await disable_expired_starter_jobs(db_session)

    assert await _state(db_session, job) == ("ACTIVE", None)


@pytest.mark.asyncio
async def test_professional_and_exempt_companies_keep_their_old_jobs(db_session):
    professional = await _company(db_session, plan="professional")
    exempt = await _company(db_session, exempt=True)
    pro_job = await _live_job(db_session, professional, days=90)
    exempt_job = await _live_job(db_session, exempt, days=90)

    await disable_expired_starter_jobs(db_session)

    assert await _state(db_session, pro_job) == ("ACTIVE", None)
    assert await _state(db_session, exempt_job) == ("ACTIVE", None)


@pytest.mark.asyncio
async def test_old_jobs_of_a_paid_company_do_not_crowd_out_a_starter_ones(db_session):
    """The sweep goes company by company, not "the oldest N jobs"."""
    professional = await _company(db_session, plan="professional")
    for _ in range(5):
        await _live_job(db_session, professional, days=400)
    starter = await _company(db_session)
    job = await _live_job(db_session, starter, days=31)

    await disable_expired_starter_jobs(db_session)

    assert await _state(db_session, job) == ("DISABLED", "EXPIRED")


@pytest.mark.asyncio
async def test_jobs_that_are_not_live_and_admin_jobs_are_not_touched(db_session):
    owner = await _company(db_session)
    closed = await _live_job(db_session, owner, days=60, status=JobStatus.CLOSED.value)
    draft = await _live_job(db_session, owner, days=60, status=JobStatus.DRAFT.value)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    admin_job = await _live_job(db_session, admin, days=60)

    await disable_expired_starter_jobs(db_session)

    assert (await _state(db_session, closed))[0] == "CLOSED"
    assert (await _state(db_session, draft))[0] == "DRAFT"
    assert (await _state(db_session, admin_job))[0] == "ACTIVE"


@pytest.mark.asyncio
async def test_running_it_again_does_nothing_more(db_session):
    owner = await _company(db_session)
    await _live_job(db_session, owner, days=31)

    await disable_expired_starter_jobs(db_session)
    await disable_expired_starter_jobs(db_session)

    told = (
        await db_session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_id == owner.id, Notification.type == "JOB_DISABLED")
        )
    ).scalar_one()
    assert told == 1  # one notification, not one per run


@pytest.mark.asyncio
async def test_nothing_happens_while_plan_gating_is_off(db_session, monkeypatch):
    """Production today: gating is off. Switching it on must be a deliberate step; until
    then no job is switched off."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    owner = await _company(db_session)
    job = await _live_job(db_session, owner, days=90)

    assert await disable_expired_starter_jobs(db_session) == 0

    assert await _state(db_session, job) == ("ACTIVE", None)
