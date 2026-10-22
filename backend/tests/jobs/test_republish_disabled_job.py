"""A job the platform switched off can be re-published once the plan allows it (on Starter the
employer is asked to upgrade), and the employer can list their disabled jobs."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.config import settings
from app.core.exceptions import PlanUpgradeRequiredException
from app.modules.ai import tasks as ai_tasks
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.billing.models import PlanGateExemption
from app.modules.jobs.enums import JobStatus
from app.modules.jobs.service import JobService
from tests.conftest import (
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    monkeypatch.setattr(ai_tasks.score_job_against_talent_pool_task, "delay", MagicMock())


async def _company_with_disabled_job(db_session, plan=None, exempt=False):
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(
        db_session, owner, company_name="Acme", is_profile_complete=True, kyc_status="APPROVED"
    )
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    if exempt:
        db_session.add(PlanGateExemption(organization_id=organization.id, reason="Pilot"))
        await db_session.flush()
    job = make_job(
        owner.id,
        status=JobStatus.DISABLED.value,
        moderation_status="APPROVED",
        published_at=datetime.now(UTC) - timedelta(days=35),
        disabled_reason="EXPIRED",
        disabled_at=datetime.now(UTC) - timedelta(days=5),
    )
    db_session.add(job)
    await db_session.flush()
    return owner, job


@pytest.mark.asyncio
async def test_a_starter_company_is_asked_to_upgrade_to_re_publish(db_session):
    owner, job = await _company_with_disabled_job(db_session)

    with pytest.raises(PlanUpgradeRequiredException):
        await JobService(db_session).publish_job(job.id, owner)

    await db_session.refresh(job)
    assert job.status == "DISABLED"  # nothing changed


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["professional", "exempt"])
async def test_a_company_with_professional_access_can_re_publish_the_same_job(db_session, how):
    owner, job = await _company_with_disabled_job(
        db_session, plan="professional" if how == "professional" else None, exempt=how == "exempt"
    )
    before = job.published_at

    published = await JobService(db_session).publish_job(job.id, owner)

    assert published.status == "ACTIVE"
    await db_session.refresh(job)
    assert job.status == "ACTIVE"
    assert job.disabled_reason is None and job.disabled_at is None
    assert job.published_at > before  # the date it went live again


@pytest.mark.asyncio
async def test_nothing_is_blocked_while_plan_gating_is_off(db_session, monkeypatch):
    """Production today: gating is off, so every company resolves to Professional."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    owner, job = await _company_with_disabled_job(db_session)

    published = await JobService(db_session).publish_job(job.id, owner)

    assert published.status == "ACTIVE"


@pytest.mark.asyncio
async def test_the_employer_can_list_only_their_disabled_jobs(client, db_session):
    owner, disabled = await _company_with_disabled_job(db_session, plan="professional")
    live = make_job(owner.id, title="Still live", status=JobStatus.ACTIVE.value)
    db_session.add(live)
    await db_session.flush()
    token = create_token_pair(owner.id, owner.role)["access_token"]

    response = await client.get(
        "/api/v1/jobs/mine", params={"filter": "disabled"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["id"] for item in items] == [str(disabled.id)]
    assert items[0]["status"] == "DISABLED"
    assert items[0]["disabled_reason"] == "EXPIRED"
    assert items[0]["disabled_at"] is not None


@pytest.mark.asyncio
async def test_a_disabled_job_can_be_closed(db_session):
    owner, job = await _company_with_disabled_job(db_session, plan="professional")

    closed = await JobService(db_session).close_job(job.id, owner)

    assert closed.status == "CLOSED"
