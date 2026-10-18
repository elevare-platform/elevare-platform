"""Credits for AI interviews.

One rule runs all of it: an interview is PAID when its charges outnumber its
refunds. So an invite charges unless the interview is already paid, a resend while
paid is free, a refund only happens while paid and only once, and an interview
that was refunded is charged again when it is invited again."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientCreditsException
from app.modules.credits.models import CreditTransaction
from app.modules.credits.repository import CreditsRepository
from app.modules.credits.service import CreditsService
from tests.conftest import make_employer, make_organization_for, test_engine

COST = 10


async def _org(db_session, balance=100):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    if balance:
        await CreditsService(db_session).grant(organization.id, balance)
    return organization


async def _ledger(db_session, organization_id, interview_id):
    statement = (
        select(CreditTransaction)
        .where(
            CreditTransaction.employer_id == organization_id,
            CreditTransaction.reference_id == interview_id,
        )
        .order_by(CreditTransaction.created_at, CreditTransaction.delta)
    )
    rows = (await db_session.execute(statement)).scalars().all()
    return [(row.reason, row.delta) for row in rows]


async def _paid(db_session, organization_id, interview_id) -> bool:
    service = CreditsService(db_session)
    return await service.has_outstanding_interview_charge(organization_id, interview_id)


@pytest.mark.asyncio
async def test_charging_takes_the_credits_and_records_the_interview(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)

    charged = await service.charge_interview(organization.id, interview_id, COST)

    assert charged is True
    assert await service.get_balance(organization.id) == 90
    assert await _ledger(db_session, organization.id, interview_id) == [
        ("interview_charge", -COST)
    ]


@pytest.mark.asyncio
async def test_charging_again_while_paid_takes_nothing_more(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, interview_id, COST)

    again = await service.charge_interview(organization.id, interview_id, COST)

    assert again is False
    assert await service.get_balance(organization.id) == 90
    assert len(await _ledger(db_session, organization.id, interview_id)) == 1


@pytest.mark.asyncio
async def test_not_enough_credits_is_refused_and_nothing_is_taken(db_session):
    organization = await _org(db_session, balance=4)
    interview_id = uuid4()
    service = CreditsService(db_session)

    with pytest.raises(InsufficientCreditsException) as raised:
        await service.charge_interview(organization.id, interview_id, COST)

    assert raised.value.code == "INSUFFICIENT_CREDITS"
    assert raised.value.status_code == 402
    # The message says what it costs and what they have.
    assert "10" in raised.value.message
    assert "4" in raised.value.message
    assert await service.get_balance(organization.id) == 4
    assert await _ledger(db_session, organization.id, interview_id) == []
    assert await _paid(db_session, organization.id, interview_id) is False


@pytest.mark.asyncio
async def test_a_refund_returns_what_was_charged_and_only_once(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, interview_id, COST)

    first = await service.refund_interview(organization.id, interview_id)
    second = await service.refund_interview(organization.id, interview_id)

    assert first == COST
    assert second == 0
    assert await service.get_balance(organization.id) == 100
    assert await _ledger(db_session, organization.id, interview_id) == [
        ("interview_charge", -COST),
        ("interview_refund", COST),
    ]


@pytest.mark.asyncio
async def test_refunding_an_interview_that_was_never_charged_does_nothing(db_session):
    organization = await _org(db_session)
    service = CreditsService(db_session)

    assert await service.refund_interview(organization.id, uuid4()) == 0
    assert await service.get_balance(organization.id) == 100


@pytest.mark.asyncio
async def test_a_refunded_interview_is_charged_again_when_invited_again(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, interview_id, COST)
    await service.refund_interview(organization.id, interview_id)

    charged = await service.charge_interview(organization.id, interview_id, COST)

    assert charged is True
    assert await service.get_balance(organization.id) == 90
    assert await _paid(db_session, organization.id, interview_id) is True


@pytest.mark.asyncio
async def test_a_refund_is_what_was_charged_even_if_the_price_has_changed(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, interview_id, 10)

    # The price later drops to 5; the employer still gets back the 10 they paid.
    refunded = await service.refund_interview(organization.id, interview_id)

    assert refunded == 10


@pytest.mark.asyncio
async def test_a_price_of_zero_charges_nothing(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)

    charged = await service.charge_interview(organization.id, interview_id, 0)

    assert charged is False
    assert await service.get_balance(organization.id) == 100
    assert await _ledger(db_session, organization.id, interview_id) == []


@pytest.mark.asyncio
async def test_paid_means_charged_and_not_refunded(db_session):
    organization = await _org(db_session)
    interview_id = uuid4()
    service = CreditsService(db_session)
    assert await _paid(db_session, organization.id, interview_id) is False

    await service.charge_interview(organization.id, interview_id, COST)
    assert await _paid(db_session, organization.id, interview_id) is True

    await service.refund_interview(organization.id, interview_id)
    assert await _paid(db_session, organization.id, interview_id) is False


@pytest.mark.asyncio
async def test_one_interview_being_paid_does_not_make_another_paid(db_session):
    organization = await _org(db_session)
    paid, other = uuid4(), uuid4()
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, paid, COST)

    assert await _paid(db_session, organization.id, other) is False


@pytest.mark.asyncio
async def test_the_balance_never_goes_below_zero_to_pay_for_an_interview(db_session):
    organization = await _org(db_session, balance=10)
    service = CreditsService(db_session)
    await service.charge_interview(organization.id, uuid4(), COST)

    with pytest.raises(InsufficientCreditsException):
        await service.charge_interview(organization.id, uuid4(), COST)

    assert await service.get_balance(organization.id) == 0


# ── Two requests at the same moment (real committed sessions) ───────────────────


async def _charge_in_own_session(organization_id, interview_id) -> str:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        try:
            await CreditsService(session).charge_interview(
                organization_id, interview_id, COST
            )
            await session.commit()
            return "charged"
        except InsufficientCreditsException:
            await session.rollback()
            return "refused"


async def _balance(organization_id) -> int:
    async with AsyncSession(test_engine) as session:
        return (
            await session.execute(
                text("SELECT balance FROM employer_credits WHERE employer_id = :o"),
                {"o": organization_id},
            )
        ).scalar_one()


async def _grant(organization_id, amount):
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        await CreditsService(session).grant(organization_id, amount)
        await session.commit()


@pytest.fixture
def slow_read(monkeypatch):
    """Widen the gap between reading the balance and writing it, so a race is
    certain instead of a matter of luck."""
    original = CreditsRepository.get_or_create_balance

    async def read_then_pause(self, *args, **kwargs):
        balance = await original(self, *args, **kwargs)
        await asyncio.sleep(0.3)
        return balance

    monkeypatch.setattr(CreditsRepository, "get_or_create_balance", read_then_pause)


@pytest.mark.asyncio
async def test_two_simultaneous_invites_for_the_same_interview_charge_once(
    committed_org, slow_read
):
    await _grant(committed_org, 100)
    interview_id = uuid4()

    await asyncio.gather(
        _charge_in_own_session(committed_org, interview_id),
        _charge_in_own_session(committed_org, interview_id),
    )

    assert await _balance(committed_org) == 90


@pytest.mark.asyncio
async def test_two_simultaneous_invites_for_different_interviews_cannot_both_use_the_last_credits(
    committed_org, slow_read
):
    await _grant(committed_org, COST)

    results = await asyncio.gather(
        _charge_in_own_session(committed_org, uuid4()),
        _charge_in_own_session(committed_org, uuid4()),
    )

    assert sorted(results) == ["charged", "refused"]
    assert await _balance(committed_org) == 0
