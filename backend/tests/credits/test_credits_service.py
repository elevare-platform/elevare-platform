"""Tests for CreditsService — ledger mutations and balance enforcement."""


import pytest

from app.core.exceptions import ValidationException
from app.modules.credits.models import CreditTransaction, EmployerCredits
from app.modules.credits.service import CreditsService
from tests.conftest import make_employer


@pytest.mark.asyncio
async def test_get_balance_returns_zero_for_new_employer(db_session):
    """get_balance creates a zero-balance row if none exists yet."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)
    balance = await service.get_balance(employer.id)

    assert balance == 0


@pytest.mark.asyncio
async def test_grant_increases_balance(db_session):
    """grant adds credits and returns the new balance."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)
    new_balance = await service.grant(employer.id, amount=5)

    assert new_balance == 5


@pytest.mark.asyncio
async def test_grant_writes_transaction_row(db_session):
    """grant persists a CreditTransaction with reason=admin_grant."""
    from sqlalchemy import select

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)
    await service.grant(employer.id, amount=3)

    result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.employer_id == employer.id)
    )
    tx = result.scalar_one()
    assert tx.delta == 3
    assert tx.reason == "admin_grant"


@pytest.mark.asyncio
async def test_deduct_decreases_balance(db_session):
    """deduct removes 1 credit and returns the new balance."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)
    await service.grant(employer.id, amount=3)
    new_balance = await service.deduct(employer.id)

    assert new_balance == 2


@pytest.mark.asyncio
async def test_deduct_raises_when_balance_zero(db_session):
    """deduct raises ValueError when the employer has no credits."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)

    with pytest.raises(ValidationException, match="Insufficient credits"):
        await service.deduct(employer.id)


@pytest.mark.asyncio
async def test_refund_restores_credit(db_session):
    """refund adds 1 credit back after a deduct."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)
    await service.grant(employer.id, amount=1)
    await service.deduct(employer.id)
    new_balance = await service.refund(employer.id)

    assert new_balance == 1


@pytest.mark.asyncio
async def test_refund_writes_transaction_row(db_session):
    """refund persists a CreditTransaction with reason=intro_refund."""
    from sqlalchemy import select

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = CreditsService(db_session)
    await service.grant(employer.id, amount=1)
    await service.deduct(employer.id)
    await service.refund(employer.id)

    result = await db_session.execute(
        select(CreditTransaction)
        .where(CreditTransaction.employer_id == employer.id)
        .where(CreditTransaction.reason == "intro_refund")
    )
    tx = result.scalar_one()
    assert tx.delta == 1


@pytest.mark.asyncio
async def test_balance_cannot_go_negative_at_db_level(db_session):
    """DB CHECK constraint prevents balance going below 0."""
    from sqlalchemy.exc import IntegrityError

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    # Bypass service and force a negative balance directly
    credits_row = EmployerCredits(employer_id=employer.id, balance=-1)
    db_session.add(credits_row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
