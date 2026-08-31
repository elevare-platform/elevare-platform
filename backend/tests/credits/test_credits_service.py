"""Tests for CreditsService — ledger mutations and balance enforcement."""

import pytest

from app.core.exceptions import ValidationException
from app.modules.credits.models import CreditTransaction, EmployerCredits
from app.modules.credits.service import CreditsService
from tests.conftest import make_employer, make_organization_for


async def make_org(db_session):
    """Create an employer + their Organization, return the Organization."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    return await make_organization_for(db_session, employer)


@pytest.mark.asyncio
async def test_get_balance_returns_zero_for_new_employer(db_session):
    """get_balance creates a zero-balance row if none exists yet."""
    organization = await make_org(db_session)

    service = CreditsService(db_session)
    balance = await service.get_balance(organization.id)

    assert balance == 0


@pytest.mark.asyncio
async def test_grant_increases_balance(db_session):
    """grant adds credits and returns the new balance."""
    organization = await make_org(db_session)

    service = CreditsService(db_session)
    new_balance = await service.grant(organization.id, amount=5)

    assert new_balance == 5


@pytest.mark.asyncio
async def test_grant_writes_transaction_row(db_session):
    """grant persists a CreditTransaction with reason=admin_grant."""
    from sqlalchemy import select

    organization = await make_org(db_session)

    service = CreditsService(db_session)
    await service.grant(organization.id, amount=3)

    result = await db_session.execute(
        select(CreditTransaction).where(
            CreditTransaction.employer_id == organization.id
        )
    )
    tx = result.scalar_one()
    assert tx.delta == 3
    assert tx.reason == "admin_grant"


@pytest.mark.asyncio
async def test_deduct_decreases_balance(db_session):
    """deduct removes 1 credit and returns the new balance."""
    organization = await make_org(db_session)

    service = CreditsService(db_session)
    await service.grant(organization.id, amount=3)
    new_balance = await service.deduct(organization.id)

    assert new_balance == 2


@pytest.mark.asyncio
async def test_deduct_raises_when_balance_zero(db_session):
    """deduct raises ValueError when the employer has no credits."""
    organization = await make_org(db_session)

    service = CreditsService(db_session)

    with pytest.raises(ValidationException, match="Insufficient credits"):
        await service.deduct(organization.id)


@pytest.mark.asyncio
async def test_refund_restores_credit(db_session):
    """refund adds 1 credit back after a deduct."""
    organization = await make_org(db_session)

    service = CreditsService(db_session)
    await service.grant(organization.id, amount=1)
    await service.deduct(organization.id)
    new_balance = await service.refund(organization.id)

    assert new_balance == 1


@pytest.mark.asyncio
async def test_refund_writes_transaction_row(db_session):
    """refund persists a CreditTransaction with reason=intro_refund."""
    from sqlalchemy import select

    organization = await make_org(db_session)

    service = CreditsService(db_session)
    await service.grant(organization.id, amount=1)
    await service.deduct(organization.id)
    await service.refund(organization.id)

    result = await db_session.execute(
        select(CreditTransaction)
        .where(CreditTransaction.employer_id == organization.id)
        .where(CreditTransaction.reason == "intro_refund")
    )
    tx = result.scalar_one()
    assert tx.delta == 1


@pytest.mark.asyncio
async def test_balance_cannot_go_negative_at_db_level(db_session):
    """DB CHECK constraint prevents balance going below 0."""
    from sqlalchemy.exc import IntegrityError

    organization = await make_org(db_session)

    # Bypass service and force a negative balance directly
    credits_row = EmployerCredits(employer_id=organization.id, balance=-1)
    db_session.add(credits_row)

    with pytest.raises(IntegrityError):
        await db_session.flush()
