"""GET /api/v1/credits/balance: the total, and the two pots it is made of."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.credits.service import CreditsService
from tests.conftest import make_subscription_for
from tests.interviews.test_interview_router import register_and_promote

URL = "/api/v1/credits/balance"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_balance_is_the_total_and_shows_both_pots(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    subscription = await make_subscription_for(
        db_session, SimpleNamespace(id=user.organization_id), plan_code="professional"
    )
    credits = CreditsService(db_session)
    await credits.grant(user.organization_id, 10)
    await credits.reset_plan_allowance(user.organization_id, 40, uuid4())

    resp = await client.get(URL, headers=_auth(token))

    assert resp.status_code == 200
    body = resp.json()
    assert (body["balance"], body["plan_credits"], body["purchased_credits"]) == (
        50,
        40,
        10,
    )
    # The plan credits are replaced when the current billing period ends.
    assert body["plan_credits_reset_at"] is not None
    assert body["plan_credits_reset_at"].startswith(
        subscription.current_period_end.strftime("%Y-%m-%dT%H:%M")
    )


@pytest.mark.asyncio
async def test_without_plan_credits_there_is_no_reset_date(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    await CreditsService(db_session).grant(user.organization_id, 5)

    resp = await client.get(URL, headers=_auth(token))

    assert resp.json() == {
        "balance": 5,
        "plan_credits": 0,
        "purchased_credits": 5,
        "plan_credits_reset_at": None,
    }
