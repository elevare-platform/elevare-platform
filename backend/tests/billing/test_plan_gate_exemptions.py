"""Companies an admin has exempted keep Professional access while plan gating is on.

Two things are tested: the plan check (does an exempt company really get Professional,
and only when it should), and the admin API that manages the list.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.exceptions import PlanUpgradeRequiredException
from app.modules.admin.models import AuditLog
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.billing.models import PlanGateExemption
from app.modules.billing.repository import BillingRepository
from app.modules.billing.service import BillingService
from app.modules.users.models import Organization, User
from tests.conftest import (
    make_admin,
    make_employer,
    make_organization_for,
    make_subscription_for,
    make_user,
    test_engine,
)

URL = "/api/v1/admin/plan-exemptions"

# Real sessions for the concurrency test. They use the tests' own engine, which keeps no
# pool: a pooled connection made inside one test's event loop would break the next test
# that reuses it.
RealSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    """The local .env turns gating off; these tests are about it being on."""
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _company(db_session, name="Acme Ltd"):
    """A company with one owner. Returns (owner, organization)."""
    owner = make_employer(email=f"owner_{uuid.uuid4().hex[:8]}@acme.example.com")
    db_session.add(owner)
    await db_session.flush()
    organization = await make_organization_for(db_session, owner, company_name=name)
    return owner, organization


async def _admin_headers(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    token = create_token_pair(admin.id, admin.role)["access_token"]
    return admin, {"Authorization": f"Bearer {token}"}


async def _exempt(db_session, organization, **overrides):
    """Put a company on the list directly, bypassing the API's input checks."""
    values = {"organization_id": organization.id, "reason": "Pilot customer"}
    values.update(overrides)
    row = PlanGateExemption(**values)
    db_session.add(row)
    await db_session.flush()
    return row


async def _plan_code(db_session, organization):
    plan = await BillingService(db_session).get_effective_plan(organization.id)
    return plan.code


def _body(email, **overrides):
    body = {"email": email, "reason": "Pilot customer for the October launch"}
    body.update(overrides)
    return body


# --- the plan check -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_free_company_with_no_exemption_is_on_starter(db_session):
    _owner, organization = await _company(db_session)

    assert await _plan_code(db_session, organization) == "starter"


@pytest.mark.asyncio
async def test_an_exempt_company_gets_professional(db_session):
    _owner, organization = await _company(db_session)
    await _exempt(db_session, organization)

    assert await _plan_code(db_session, organization) == "professional"


@pytest.mark.asyncio
async def test_an_exemption_with_a_future_end_date_still_applies(db_session):
    _owner, organization = await _company(db_session)
    await _exempt(db_session, organization, expires_at=datetime.now(UTC) + timedelta(days=5))

    assert await _plan_code(db_session, organization) == "professional"


@pytest.mark.asyncio
async def test_an_exemption_whose_end_date_has_passed_no_longer_applies(db_session):
    _owner, organization = await _company(db_session)
    await _exempt(db_session, organization, expires_at=datetime.now(UTC) - timedelta(minutes=1))

    assert await _plan_code(db_session, organization) == "starter"


@pytest.mark.asyncio
async def test_exempting_one_company_does_not_change_another(db_session):
    _owner_a, exempt_company = await _company(db_session, "Exempt Ltd")
    _owner_b, other_company = await _company(db_session, "Other Ltd")
    await _exempt(db_session, exempt_company)

    assert await _plan_code(db_session, exempt_company) == "professional"
    assert await _plan_code(db_session, other_company) == "starter"


@pytest.mark.asyncio
async def test_an_exemption_never_lowers_a_paying_enterprise_company(db_session):
    """Being on the list must not take away something the company pays for."""
    _owner, organization = await _company(db_session)
    await make_subscription_for(db_session, organization, plan_code="enterprise")
    await _exempt(db_session, organization)

    assert await _plan_code(db_session, organization) == "enterprise"


@pytest.mark.asyncio
async def test_the_professional_gate_lets_an_exempt_company_through_and_blocks_others(
    db_session,
):
    _owner_a, exempt_company = await _company(db_session, "Exempt Ltd")
    _owner_b, other_company = await _company(db_session, "Other Ltd")
    await _exempt(db_session, exempt_company)
    billing = BillingService(db_session)

    await billing.assert_professional_or_above(exempt_company.id)  # no error
    with pytest.raises(PlanUpgradeRequiredException):
        await billing.assert_professional_or_above(other_company.id)


# --- who may use the API -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_employer_cannot_use_the_exemption_api(client, db_session):
    owner, organization = await _company(db_session)
    token = create_token_pair(owner.id, owner.role)["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert (await client.get(URL, headers=headers)).status_code == 403
    assert (
        await client.post(URL, json=_body(owner.email), headers=headers)
    ).status_code == 403
    assert (await client.delete(f"{URL}/{organization.id}", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_the_api_needs_a_login(client):
    assert (await client.get(URL)).status_code == 401


# --- adding --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_admin_adds_a_company_by_a_members_email(client, db_session):
    admin, headers = await _admin_headers(db_session)
    owner, organization = await _company(db_session, "Acme Ltd")

    response = await client.post(URL, json=_body(owner.email), headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["organization_id"] == str(organization.id)
    assert body["company_name"] == "Acme Ltd"
    assert body["reason"] == "Pilot customer for the October launch"
    assert body["granted_by"] == str(admin.id)
    assert body["expires_at"] is None
    assert body["is_active"] is True
    assert await _plan_code(db_session, organization) == "professional"


@pytest.mark.asyncio
async def test_adding_writes_an_audit_entry(client, db_session):
    admin, headers = await _admin_headers(db_session)
    owner, organization = await _company(db_session)

    await client.post(URL, json=_body(owner.email), headers=headers)

    entry = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "ADD_PLAN_EXEMPTION",
                AuditLog.target_id == organization.id,
            )
        )
    ).scalar_one()
    assert entry.admin_id == admin.id
    assert entry.reason == "Pilot customer for the October launch"
    assert entry.log_metadata["email"] == owner.email
    assert entry.log_metadata["renewed"] is False


@pytest.mark.asyncio
async def test_the_email_is_matched_ignoring_upper_and_lower_case(client, db_session):
    _admin, headers = await _admin_headers(db_session)
    owner, organization = await _company(db_session)

    response = await client.post(URL, json=_body(owner.email.upper()), headers=headers)

    assert response.status_code == 201
    assert response.json()["organization_id"] == str(organization.id)


@pytest.mark.asyncio
async def test_an_unknown_email_is_a_404(client, db_session):
    _admin, headers = await _admin_headers(db_session)

    response = await client.post(
        URL, json=_body(f"nobody_{uuid.uuid4().hex[:8]}@example.com"), headers=headers
    )

    assert response.status_code == 404
    assert response.json()["code"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_an_account_without_a_company_is_refused(client, db_session):
    """A candidate has no plan, so there is nothing to exempt."""
    _admin, headers = await _admin_headers(db_session)
    candidate = make_user(role="CANDIDATE")
    db_session.add(candidate)
    await db_session.flush()

    response = await client.post(URL, json=_body(candidate.email), headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == "NOT_A_COMPANY_ACCOUNT"


@pytest.mark.asyncio
async def test_an_end_date_in_the_past_is_refused(client, db_session):
    _admin, headers = await _admin_headers(db_session)
    owner, _organization = await _company(db_session)
    yesterday = (datetime.now(UTC) - timedelta(days=1)).isoformat()

    response = await client.post(
        URL, json=_body(owner.email, expires_at=yesterday), headers=headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_an_end_date_without_a_timezone_is_refused(client, db_session):
    _admin, headers = await _admin_headers(db_session)
    owner, _organization = await _company(db_session)
    no_zone = (datetime.now(UTC) + timedelta(days=3)).replace(tzinfo=None).isoformat()

    response = await client.post(
        URL, json=_body(owner.email, expires_at=no_zone), headers=headers
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["", "  ", "ab", "x" * 501])
async def test_a_missing_or_badly_sized_reason_is_refused(client, db_session, reason):
    _admin, headers = await _admin_headers(db_session)
    owner, _organization = await _company(db_session)

    response = await client.post(URL, json=_body(owner.email, reason=reason), headers=headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_adding_the_same_company_twice_renews_it_and_keeps_one_row(client, db_session):
    _admin, headers = await _admin_headers(db_session)
    owner, organization = await _company(db_session)
    next_month = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    await client.post(URL, json=_body(owner.email, reason="First reason"), headers=headers)
    second = await client.post(
        URL,
        json=_body(owner.email, reason="Extended after the demo", expires_at=next_month),
        headers=headers,
    )

    assert second.status_code == 201
    rows = (
        await db_session.execute(
            select(PlanGateExemption).where(PlanGateExemption.organization_id == organization.id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].reason == "Extended after the demo"
    assert rows[0].expires_at is not None
    entries = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "ADD_PLAN_EXEMPTION", AuditLog.target_id == organization.id
            )
        )
    ).scalars().all()
    # One entry for the first add, one for the renewal.
    assert sorted(e.log_metadata["renewed"] for e in entries) == [False, True]


# --- removing ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_removing_puts_the_company_back_on_starter_and_is_audited(client, db_session):
    admin, headers = await _admin_headers(db_session)
    _owner, organization = await _company(db_session)
    await _exempt(db_session, organization, reason="Pilot customer")
    assert await _plan_code(db_session, organization) == "professional"

    response = await client.delete(f"{URL}/{organization.id}", headers=headers)

    assert response.status_code == 204
    assert await _plan_code(db_session, organization) == "starter"
    entry = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "REMOVE_PLAN_EXEMPTION",
                AuditLog.target_id == organization.id,
            )
        )
    ).scalar_one()
    assert entry.admin_id == admin.id
    assert entry.log_metadata["previous_reason"] == "Pilot customer"


@pytest.mark.asyncio
async def test_removing_a_company_that_is_not_listed_is_a_404(client, db_session):
    _admin, headers = await _admin_headers(db_session)
    _owner, organization = await _company(db_session)

    response = await client.delete(f"{URL}/{organization.id}", headers=headers)

    assert response.status_code == 404
    assert response.json()["code"] == "PLAN_EXEMPTION_NOT_FOUND"


# --- listing -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_list_is_paged_newest_first_and_marks_ended_exemptions(client, db_session):
    _admin, headers = await _admin_headers(db_session)
    _o1, first = await _company(db_session, "First Ltd")
    _o2, second = await _company(db_session, "Second Ltd")
    _o3, third = await _company(db_session, "Third Ltd")
    now = datetime.now(UTC)
    await _exempt(db_session, first, created_at=now - timedelta(hours=3))
    await _exempt(
        db_session,
        second,
        created_at=now - timedelta(hours=2),
        expires_at=now - timedelta(hours=1),
    )
    await _exempt(db_session, third, created_at=now - timedelta(hours=1))

    everything = (await client.get(URL, params={"limit": 100}, headers=headers)).json()
    ours = [i for i in everything["items"] if i["company_name"] in ("First Ltd", "Second Ltd", "Third Ltd")]
    assert [i["company_name"] for i in ours] == ["Third Ltd", "Second Ltd", "First Ltd"]
    assert {i["company_name"]: i["is_active"] for i in ours} == {
        "First Ltd": True,
        "Second Ltd": False,  # the end date has passed
        "Third Ltd": True,
    }

    page = (await client.get(URL, params={"limit": 1, "offset": 1}, headers=headers)).json()
    assert len(page["items"]) == 1
    assert page["limit"] == 1
    assert page["offset"] == 1
    assert page["total"] == everything["total"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
async def test_the_list_refuses_a_bad_page_size(client, db_session, params):
    _admin, headers = await _admin_headers(db_session)

    assert (await client.get(URL, params=params, headers=headers)).status_code == 422


# --- two at the same moment ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_three_admins_adding_the_same_company_at_once_make_one_row():
    """Real, separate database sessions and real commits: the database's own unique rule
    plus the single INSERT ... ON CONFLICT statement leave exactly one row, with no crash.
    (Everything it creates is deleted again.)"""
    owner_id = admin_id = organization_id = None
    try:
        async with RealSession() as setup:
            admin = make_admin()
            owner = make_employer()
            setup.add_all([admin, owner])
            await setup.flush()
            organization = await make_organization_for(setup, owner, company_name="Race Ltd")
            await setup.commit()
            admin_id, owner_id, organization_id = admin.id, owner.id, organization.id

        async def add(reason):
            async with RealSession() as session:
                await BillingRepository(session).upsert_exemption(
                    organization_id=organization_id,
                    reason=reason,
                    granted_by=admin_id,
                    expires_at=None,
                )
                await session.commit()

        await asyncio.gather(add("one"), add("two"), add("three"))

        async with RealSession() as check:
            count = (
                await check.execute(
                    select(func.count())
                    .select_from(PlanGateExemption)
                    .where(PlanGateExemption.organization_id == organization_id)
                )
            ).scalar_one()
        assert count == 1
    finally:
        async with RealSession() as cleanup:
            if organization_id:
                await cleanup.execute(
                    delete(PlanGateExemption).where(
                        PlanGateExemption.organization_id == organization_id
                    )
                )
            for user_id in (owner_id, admin_id):
                if user_id:
                    await cleanup.execute(delete(User).where(User.id == user_id))
            if organization_id:
                await cleanup.execute(delete(Organization).where(Organization.id == organization_id))
            await cleanup.commit()
