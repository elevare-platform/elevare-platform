"""A plan's monthly credits.

An organization holds two pots: plan credits (included in the plan, replaced at
each renewal, wiped when the subscription lapses) and bought credits (never
expire). Spending takes plan credits first; a refund returns to the pot it came
from."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientCreditsException, ValidationException
from app.modules.credits.models import CreditTransaction
from app.modules.credits.service import CreditsService
from tests.conftest import make_employer, make_organization_for, test_engine

COST = 10


async def _org(db_session, *, plan=0, bought=0):
    """An organization holding ``plan`` plan credits and ``bought`` bought ones."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    service = CreditsService(db_session)
    if bought:
        await service.grant(organization.id, bought)
    if plan:
        await service.reset_plan_allowance(organization.id, plan, uuid4())
    return organization


async def _pots(db_session, organization):
    balances = await CreditsService(db_session).get_balances(organization.id)
    return balances["plan_credits"], balances["purchased_credits"]


async def _ledger_sum(db_session, organization_id) -> int:
    return (
        await db_session.execute(
            select(func.coalesce(func.sum(CreditTransaction.delta), 0)).where(
                CreditTransaction.employer_id == organization_id
            )
        )
    ).scalar_one()


async def _rows(db_session, organization_id, reason):
    return (
        (
            await db_session.execute(
                select(CreditTransaction).where(
                    CreditTransaction.employer_id == organization_id,
                    CreditTransaction.reason == reason,
                )
            )
        )
        .scalars()
        .all()
    )


@pytest.mark.asyncio
async def test_a_deposit_adds_plan_credits_and_leaves_bought_credits_alone(db_session):
    organization = await _org(db_session, bought=7)

    deposited = await CreditsService(db_session).reset_plan_allowance(
        organization.id, 40, uuid4()
    )

    assert deposited is True
    assert await _pots(db_session, organization) == (40, 7)


@pytest.mark.asyncio
async def test_a_grant_goes_to_bought_credits_not_plan_credits(db_session):
    organization = await _org(db_session, plan=40)

    total = await CreditsService(db_session).grant(organization.id, 10)

    assert total == 50
    assert await _pots(db_session, organization) == (40, 10)


@pytest.mark.asyncio
async def test_spending_takes_plan_credits_first_then_bought(db_session):
    organization = await _org(db_session, plan=6, bought=10)
    service = CreditsService(db_session)
    interview_id = uuid4()

    await service.charge_interview(organization.id, interview_id, COST)

    assert await _pots(db_session, organization) == (0, 6)
    charge = (await _rows(db_session, organization.id, "interview_charge"))[0]
    assert (charge.delta, charge.plan_portion) == (-10, 6)


@pytest.mark.asyncio
async def test_spending_less_than_the_plan_credits_leaves_bought_untouched(db_session):
    organization = await _org(db_session, plan=40, bought=10)

    await CreditsService(db_session).charge_interview(organization.id, uuid4(), COST)

    assert await _pots(db_session, organization) == (30, 10)


@pytest.mark.asyncio
async def test_the_balance_is_the_total_of_both_pots(db_session):
    organization = await _org(db_session, plan=30, bought=5)
    service = CreditsService(db_session)

    assert await service.get_balance(organization.id) == 35
    assert await service.get_balances(organization.id) == {
        "total": 35,
        "plan_credits": 30,
        "purchased_credits": 5,
    }


@pytest.mark.asyncio
async def test_an_interview_can_use_both_pots_but_not_more_than_their_total(
    db_session,
):
    organization = await _org(db_session, plan=6, bought=3)

    with pytest.raises(InsufficientCreditsException):
        await CreditsService(db_session).charge_interview(
            organization.id, uuid4(), COST
        )

    assert await _pots(db_session, organization) == (6, 3)


@pytest.mark.asyncio
async def test_an_introduction_credit_is_also_taken_from_plan_credits_first(
    db_session,
):
    organization = await _org(db_session, plan=1, bought=5)
    service = CreditsService(db_session)

    await service.deduct(organization.id)
    assert await _pots(db_session, organization) == (0, 5)

    await service.deduct(organization.id)
    assert await _pots(db_session, organization) == (0, 4)


@pytest.mark.asyncio
async def test_overspending_through_the_ledger_is_refused_and_changes_nothing(
    db_session,
):
    organization = await _org(db_session, plan=1, bought=1)
    service = CreditsService(db_session)
    await service.deduct(organization.id)
    await service.deduct(organization.id)

    with pytest.raises(ValidationException, match="Insufficient credits"):
        await service.deduct(organization.id)

    assert await _pots(db_session, organization) == (0, 0)


@pytest.mark.asyncio
async def test_a_renewal_replaces_what_is_left_of_the_plan_credits(db_session):
    organization = await _org(db_session, plan=40, bought=10)
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, uuid4(), 25)  # 15 plan left

    await service.reset_plan_allowance(organization.id, 40, uuid4())

    assert await _pots(db_session, organization) == (40, 10)  # not 55
    wipes = await _rows(db_session, organization.id, "plan_allowance_expiry")
    # The setup deposit wiped nothing (0); the renewal wiped the 15 left.
    assert sorted(row.delta for row in wipes) == [-15, 0]


@pytest.mark.asyncio
async def test_the_same_payment_only_ever_deposits_once(db_session):
    organization = await _org(db_session)
    service = CreditsService(db_session)
    payment_id = uuid4()

    first = await service.reset_plan_allowance(organization.id, 40, payment_id)
    await service.charge_interview(organization.id, uuid4(), COST)
    second = await service.reset_plan_allowance(organization.id, 40, payment_id)

    assert (first, second) == (True, False)
    # The retry did not top the pot back up.
    assert await _pots(db_session, organization) == (30, 0)
    assert len(await _rows(db_session, organization.id, "plan_allowance")) == 1


@pytest.mark.asyncio
async def test_a_plan_with_no_included_credits_deposits_nothing(db_session):
    organization = await _org(db_session, bought=4)

    deposited = await CreditsService(db_session).reset_plan_allowance(
        organization.id, 0, uuid4()
    )

    assert deposited is False
    assert await _pots(db_session, organization) == (0, 4)
    assert await _rows(db_session, organization.id, "plan_allowance") == []


@pytest.mark.asyncio
async def test_a_lapsed_subscription_loses_plan_credits_but_keeps_bought_ones(
    db_session,
):
    organization = await _org(db_session, plan=40, bought=10)
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, uuid4(), COST)  # 30 plan left

    wiped = await service.expire_plan_allowance(organization.id)

    assert wiped == 30
    assert await _pots(db_session, organization) == (0, 10)


@pytest.mark.asyncio
async def test_expiring_with_nothing_left_still_leaves_a_marker(db_session):
    organization = await _org(db_session, bought=3)
    service = CreditsService(db_session)

    wiped = await service.expire_plan_allowance(organization.id)

    assert wiped == 0
    assert len(await _rows(db_session, organization.id, "plan_allowance_expiry")) == 1


@pytest.mark.asyncio
async def test_the_ledger_always_adds_up_to_both_pots(db_session):
    organization = await _org(db_session, plan=40, bought=10)
    service = CreditsService(db_session)
    interview_id = uuid4()
    await service.charge_interview(organization.id, interview_id, 45)
    await service.refund_interview(organization.id, interview_id)
    await service.deduct(organization.id)
    await service.reset_plan_allowance(organization.id, 40, uuid4())
    await service.expire_plan_allowance(organization.id)

    plan, bought = await _pots(db_session, organization)
    assert plan + bought == await _ledger_sum(db_session, organization.id)


# --- refunds go back to the pot they came from --------------------------------


@pytest.mark.asyncio
async def test_a_refund_returns_credits_to_the_pots_they_came_from(db_session):
    organization = await _org(db_session, plan=6, bought=10)
    service = CreditsService(db_session)
    interview_id = uuid4()
    await service.charge_interview(organization.id, interview_id, COST)
    assert await _pots(db_session, organization) == (0, 6)

    refunded = await service.refund_interview(organization.id, interview_id)

    assert refunded == 10
    assert await _pots(db_session, organization) == (6, 10)


@pytest.mark.asyncio
async def test_a_refund_after_a_renewal_returns_the_plan_part_as_bought_credits(
    db_session,
):
    """The plan credits it was paid with no longer exist; the customer is made
    whole, and the fresh allowance does not end up above what the plan includes."""
    organization = await _org(db_session, plan=40)
    service = CreditsService(db_session)
    interview_id = uuid4()
    await service.charge_interview(organization.id, interview_id, COST)

    await service.reset_plan_allowance(organization.id, 40, uuid4())  # renewal
    await service.refund_interview(organization.id, interview_id)

    assert await _pots(db_session, organization) == (40, 10)


@pytest.mark.asyncio
async def test_a_refund_after_the_subscription_lapsed_does_not_revive_plan_credits(
    db_session,
):
    organization = await _org(db_session, plan=40)
    service = CreditsService(db_session)
    interview_id = uuid4()
    await service.charge_interview(organization.id, interview_id, COST)
    await service.expire_plan_allowance(organization.id)  # wipes the 30 left

    await service.refund_interview(organization.id, interview_id)

    assert await _pots(db_session, organization) == (0, 10)


@pytest.mark.asyncio
async def test_a_refunded_introduction_credit_is_a_bought_credit(db_session):
    organization = await _org(db_session, plan=1)
    service = CreditsService(db_session)
    await service.deduct(organization.id)

    total = await service.refund(organization.id, reference_id=uuid4())

    assert total == 1
    assert await _pots(db_session, organization) == (0, 1)


# --- two requests at the same moment -------------------------------------------


@pytest.fixture
def two_sessions():
    class _Sessions:
        async def run(self, work):
            async with AsyncSession(test_engine, expire_on_commit=False) as session:
                try:
                    result = await work(CreditsService(session))
                    await session.commit()
                    return result
                except Exception:
                    await session.rollback()
                    raise

    return _Sessions()


async def _read_pots(organization_id):
    async with AsyncSession(test_engine) as session:
        row = (
            await session.execute(
                text(
                    "SELECT plan_balance, balance FROM employer_credits "
                    "WHERE employer_id = :o"
                ),
                {"o": organization_id},
            )
        ).one()
        return row.plan_balance, row.balance


@pytest.mark.asyncio
async def test_two_deliveries_of_the_same_payment_deposit_once(
    committed_org, two_sessions
):
    payment_id = uuid4()

    results = await asyncio.gather(
        two_sessions.run(lambda s: s.reset_plan_allowance(committed_org, 40, payment_id)),
        two_sessions.run(lambda s: s.reset_plan_allowance(committed_org, 40, payment_id)),
    )

    assert sorted(results) == [False, True]
    assert await _read_pots(committed_org) == (40, 0)


@pytest.mark.asyncio
async def test_two_spends_at_once_cannot_spend_more_than_both_pots_hold(
    committed_org, two_sessions
):
    await two_sessions.run(lambda s: s.grant(committed_org, 4))
    await two_sessions.run(lambda s: s.reset_plan_allowance(committed_org, 6, uuid4()))

    async def spend(service):
        try:
            await service.charge_interview(committed_org, uuid4(), COST)
            return True
        except InsufficientCreditsException:
            return False

    results = await asyncio.gather(
        two_sessions.run(spend), two_sessions.run(spend)
    )

    assert sorted(results) == [False, True]
    assert await _read_pots(committed_org) == (0, 0)
