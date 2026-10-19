"""The credit history an organization sees (GET /api/v1/credits/transactions)."""

from uuid import uuid4

import pytest

from app.modules.billing.models import Payment
from app.modules.credits.history import CreditHistoryService
from app.modules.credits.service import CreditsService
from tests.conftest import make_employer, make_job, make_organization_for
from tests.interviews.conftest import make_interview, make_talent_pool_profile
from tests.interviews.test_interview_router import register_and_promote

URL = "/api/v1/credits/transactions"


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _org(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    return employer, organization


async def _history(db_session, organization, **kwargs):
    return await CreditHistoryService(db_session).get_history(organization.id, **kwargs)


@pytest.mark.asyncio
async def test_history_is_newest_first_in_plain_words(db_session):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 5)  # a gift: no payment behind it
    await credits.reset_plan_allowance(organization.id, 40, uuid4())
    await credits.deduct(organization.id)

    page = await _history(db_session, organization)

    assert [(item.kind, item.description) for item in page.items] == [
        ("introduction", "Introduction requested"),
        ("plan_credits", "Monthly plan credits"),
        ("grant", "Credits added by Elevare"),
    ]
    assert page.next_cursor is None


@pytest.mark.asyncio
async def test_each_line_says_which_pot_it_moved(db_session):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 4)
    await credits.reset_plan_allowance(organization.id, 6, uuid4())
    await credits.charge_interview(organization.id, uuid4(), 10)  # 6 plan + 4 bought

    page = await _history(db_session, organization)

    spend, deposit, grant = page.items
    assert (spend.credits_change, spend.plan_credits_change, spend.purchased_credits_change) == (
        -10,
        -6,
        -4,
    )
    assert (deposit.credits_change, deposit.plan_credits_change, deposit.purchased_credits_change) == (
        6,
        6,
        0,
    )
    assert (grant.credits_change, grant.plan_credits_change, grant.purchased_credits_change) == (
        4,
        0,
        4,
    )


@pytest.mark.asyncio
async def test_a_refund_shows_the_credits_coming_back_to_their_pots(db_session):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 4)
    await credits.reset_plan_allowance(organization.id, 6, uuid4())
    interview_id = uuid4()
    await credits.charge_interview(organization.id, interview_id, 10)
    await credits.refund_interview(organization.id, interview_id)

    refund = (await _history(db_session, organization)).items[0]

    assert refund.kind == "interview_refund"
    assert (refund.credits_change, refund.plan_credits_change, refund.purchased_credits_change) == (
        10,
        6,
        4,
    )


@pytest.mark.asyncio
async def test_a_paid_pack_is_told_apart_from_a_gift(db_session):
    employer, organization = await _org(db_session)
    payment = Payment(
        organization_id=organization.id,
        purpose="CREDIT_TOPUP",
        amount_kobo=1_500_000,
        currency="NGN",
        status="SUCCEEDED",
        provider="PAYSTACK",
        provider_reference=f"PSK_history_{uuid4().hex}",
        credits_granted=10,
    )
    db_session.add(payment)
    await db_session.flush()
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 10, reference_id=payment.id)
    await credits.grant(organization.id, 3)

    page = await _history(db_session, organization)

    assert [item.description for item in page.items] == [
        "Credits added by Elevare",
        "Credit pack purchased",
    ]


@pytest.mark.asyncio
async def test_an_interview_line_says_which_job_it_was_for(db_session):
    employer, organization = await _org(db_session)
    job = make_job(employer.id, title="Senior Accountant")
    db_session.add(job)
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, employer.id)
    interview = await make_interview(db_session, job.id, profile.id)
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 20)
    await credits.charge_interview(organization.id, interview.id, 10)

    page = await _history(db_session, organization)

    assert page.items[0].description == "AI interview invite"
    assert page.items[0].detail == "Senior Accountant"
    assert page.items[1].detail is None  # the grant was not for a job


@pytest.mark.asyncio
async def test_the_markers_left_when_plan_credits_are_replaced_are_not_history(
    db_session,
):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    await credits.reset_plan_allowance(organization.id, 40, uuid4())
    await credits.expire_plan_allowance(organization.id)  # wipes 40
    await credits.expire_plan_allowance(organization.id)  # nothing left: a 0 marker

    page = await _history(db_session, organization)

    assert [item.kind for item in page.items] == ["plan_credits_expired", "plan_credits"]


@pytest.mark.asyncio
async def test_an_organization_only_ever_sees_its_own_history(db_session):
    _, mine = await _org(db_session)
    _, theirs = await _org(db_session)
    credits = CreditsService(db_session)
    await credits.grant(mine.id, 1)
    await credits.grant(theirs.id, 99)

    page = await _history(db_session, mine)

    assert [item.credits_change for item in page.items] == [1]


@pytest.mark.asyncio
async def test_pages_follow_one_another_without_repeats_or_gaps(db_session):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    for amount in range(1, 6):
        await credits.grant(organization.id, amount)

    first = await _history(db_session, organization, limit=2)
    second = await _history(db_session, organization, limit=2, cursor=first.next_cursor)
    third = await _history(db_session, organization, limit=2, cursor=second.next_cursor)

    seen = [item.credits_change for page in (first, second, third) for item in page.items]
    assert seen == [5, 4, 3, 2, 1]
    assert first.next_cursor and second.next_cursor
    assert third.next_cursor is None


@pytest.mark.asyncio
async def test_new_activity_while_browsing_does_not_shift_the_next_page(db_session):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    for amount in (1, 2, 3):
        await credits.grant(organization.id, amount)
    first = await _history(db_session, organization, limit=2)  # 3, 2

    await credits.grant(organization.id, 100)  # arrives while the first page is open
    second = await _history(db_session, organization, limit=2, cursor=first.next_cursor)

    assert [item.credits_change for item in second.items] == [1]


@pytest.mark.asyncio
async def test_a_page_never_exceeds_the_maximum_size(db_session):
    _, organization = await _org(db_session)
    credits = CreditsService(db_session)
    for _ in range(3):
        await credits.grant(organization.id, 1)

    page = await _history(db_session, organization, limit=10_000)

    assert len(page.items) == 3


# --- over HTTP ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_endpoint_returns_the_callers_own_history(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    await CreditsService(db_session).grant(user.organization_id, 7)

    resp = await client.get(URL, headers=_auth(token))

    assert resp.status_code == 200
    body = resp.json()
    assert body["next_cursor"] is None
    assert [(i["kind"], i["credits_change"]) for i in body["items"]] == [("grant", 7)]


@pytest.mark.asyncio
async def test_the_endpoint_pages_with_the_cursor(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    credits = CreditsService(db_session)
    for amount in (1, 2, 3):
        await credits.grant(user.organization_id, amount)

    first = (await client.get(URL, params={"limit": 2}, headers=_auth(token))).json()
    second = (
        await client.get(
            URL, params={"limit": 2, "cursor": first["next_cursor"]}, headers=_auth(token)
        )
    ).json()

    assert [i["credits_change"] for i in first["items"]] == [3, 2]
    assert [i["credits_change"] for i in second["items"]] == [1]


@pytest.mark.asyncio
async def test_a_bad_cursor_is_refused(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    resp = await client.get(URL, params={"cursor": "not-a-cursor"}, headers=_auth(token))

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_the_endpoint_needs_a_signed_in_employer(client, db_session):
    assert (await client.get(URL)).status_code in (401, 403)
    candidate_token, _ = await register_and_promote(client, db_session, "CANDIDATE")

    resp = await client.get(URL, headers=_auth(candidate_token))

    assert resp.status_code == 403
