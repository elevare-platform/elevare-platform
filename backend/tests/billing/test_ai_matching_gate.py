"""AI Talent Matches are Professional and above (plan 15.2 gap G1, decided 2026-10-21).

A Starter company is refused on all three match endpoints, is not sent the "new
candidates match your job" notification for matches it cannot open, and a Professional
company, an exempt company and an admin are unaffected.
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.modules.ai.tasks import _employer_has_ai_matching, _notify_employer_new_matches
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.billing.models import PlanGateExemption
from app.modules.notifications.models import Notification
from tests.conftest import (
    make_admin,
    make_employer,
    make_organization_for,
    make_subscription_for,
)


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    """The local .env turns gating off; these tests are about it being on."""
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


def _urls():
    job_id = uuid.uuid4()
    return [
        f"/api/v1/jobs/{job_id}/talent-matches",
        f"/api/v1/talent-pool/matches/{job_id}",
        f"/api/v1/talent-pool/matches/{job_id}/new-count",
    ]


async def _company(db_session, plan=None, exempt=False):
    """An employer with a company. Returns (employer, request headers)."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    if exempt:
        db_session.add(
            PlanGateExemption(organization_id=organization.id, reason="Pilot customer")
        )
        await db_session.flush()
    token = create_token_pair(employer.id, employer.role)["access_token"]
    return employer, {"Authorization": f"Bearer {token}"}


# --- the three endpoints -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_starter_company_is_refused_on_every_match_endpoint(client, db_session):
    _employer, headers = await _company(db_session)

    for url in _urls():
        response = await client.get(url, headers=headers)
        assert response.status_code == 403, url
        assert response.json()["code"] == "PLAN_UPGRADE_REQUIRED", url


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["professional", "exempt"])
async def test_a_company_with_professional_access_passes_the_gate(client, db_session, how):
    _employer, headers = await _company(
        db_session, plan="professional" if how == "professional" else None, exempt=how == "exempt"
    )

    for url in _urls():
        response = await client.get(url, headers=headers)
        # Past the plan gate: whatever comes next (a missing job, for example) is not a 403
        # about the plan.
        assert response.json().get("code") != "PLAN_UPGRADE_REQUIRED", url


@pytest.mark.asyncio
async def test_an_admin_is_not_held_back_by_the_gate(client, db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    token = create_token_pair(admin.id, admin.role)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for url in _urls():
        response = await client.get(url, headers=headers)
        assert response.json().get("code") != "PLAN_UPGRADE_REQUIRED", url


# --- the "new candidates match your job" notification --------------------------------------


@pytest.mark.asyncio
async def test_the_helper_says_yes_to_professional_exempt_and_admin_and_no_to_starter(db_session):
    starter, _ = await _company(db_session)
    professional, _ = await _company(db_session, plan="professional")
    exempt, _ = await _company(db_session, exempt=True)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()

    assert await _employer_has_ai_matching(db_session, starter.id) is False
    assert await _employer_has_ai_matching(db_session, professional.id) is True
    assert await _employer_has_ai_matching(db_session, exempt.id) is True
    assert await _employer_has_ai_matching(db_session, admin.id) is True


@pytest.mark.asyncio
async def test_a_starter_company_is_not_notified_about_matches_it_cannot_open(db_session):
    starter, _ = await _company(db_session)

    # Returns before it searches anything, so any non-empty embedding will do.
    await _notify_employer_new_matches(
        db_session, starter.id, uuid.uuid4(), [0.1, 0.2, 0.3], "Senior Engineer"
    )

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.recipient_id == starter.id)
        )
    ).scalar_one()
    assert count == 0
