"""Credit balance changes must be safe when two requests arrive at the same moment.

Before the balance row was locked, two requests could both read the last credit,
both pass the "enough credits" check, and both write, so one spend was free.
The race tests use two real, committed database sessions (the usual per-test
rollback session cannot show a race) and clean up after themselves.
"""

import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.credits.repository import CreditsRepository
from app.modules.credits.service import CreditsService
from tests.conftest import make_employer, make_organization_for, test_engine

# The committed_org fixture is in conftest.py.


async def _grant(organization_id, amount) -> int:
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        balance = await CreditsService(session).grant(organization_id, amount)
        await session.commit()
        return balance


async def _try_deduct(organization_id) -> bool:
    """Spend one credit in its own session and transaction. True if it worked."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        try:
            await CreditsService(session).deduct(organization_id)
            await session.commit()
            return True
        except ValidationException:
            await session.rollback()
            return False


async def _read_balance(organization_id) -> int:
    async with AsyncSession(test_engine) as session:
        return (
            await session.execute(
                text("SELECT balance FROM employer_credits WHERE employer_id = :o"),
                {"o": organization_id},
            )
        ).scalar_one()


async def _count_ledger_rows(organization_id, reason) -> int:
    async with AsyncSession(test_engine) as session:
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM credit_transactions "
                    "WHERE employer_id = :o AND reason = :r"
                ),
                {"o": organization_id, "r": reason},
            )
        ).scalar_one()


@pytest.mark.asyncio
async def test_two_simultaneous_spends_of_the_last_credit_only_one_wins(
    committed_org, monkeypatch
):
    await _grant(committed_org, 1)

    # Widen the window between "read the balance" and "write it" so the race is
    # certain, not a matter of luck. With the row locked, the second request waits
    # at the read until the first has finished.
    original = CreditsRepository.get_or_create_balance

    async def read_then_pause(self, *args, **kwargs):
        balance = await original(self, *args, **kwargs)
        await asyncio.sleep(0.3)
        return balance

    monkeypatch.setattr(CreditsRepository, "get_or_create_balance", read_then_pause)

    results = await asyncio.gather(
        _try_deduct(committed_org), _try_deduct(committed_org)
    )

    assert sorted(results) == [False, True]
    assert await _read_balance(committed_org) == 0
    assert await _count_ledger_rows(committed_org, "intro_request") == 1


@pytest.mark.asyncio
async def test_two_first_ever_grants_at_once_both_succeed(committed_org):
    """A brand-new organization has no balance row yet. Two requests creating it
    at the same moment must not crash on the one-row-per-organization rule."""
    await asyncio.gather(_grant(committed_org, 1), _grant(committed_org, 2))

    assert await _read_balance(committed_org) == 3


@pytest.mark.asyncio
async def test_a_balance_loaded_earlier_does_not_hide_a_newer_one(db_session):
    """Regression guard: a balance loaded earlier in the request must not be
    trusted when spending; the locked read has to see what the database holds
    now. (SQLAlchemy already refreshed the copy in this scenario before the lock
    existed, so this keeps that true rather than proving a bug.)"""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)

    service = CreditsService(db_session)
    await service.grant(organization.id, 5)
    assert await service.get_balance(organization.id) == 5  # now loaded in memory

    # Another request spends everything, behind this session's back.
    await db_session.execute(
        text("UPDATE employer_credits SET balance = 0 WHERE employer_id = :o"),
        {"o": organization.id},
    )

    with pytest.raises(ValidationException):
        await service.deduct(organization.id)
