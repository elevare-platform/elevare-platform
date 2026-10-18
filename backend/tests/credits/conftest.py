"""Fixtures shared by the credits tests."""

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import make_employer, make_organization_for, test_engine


@pytest_asyncio.fixture
async def committed_org():
    """An organization that really exists in the database (committed), removed
    again afterwards. Yields the organization id.

    The usual per-test session is rolled back and cannot show a race between two
    requests, so the race tests use two real, committed sessions."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        employer = make_employer()
        session.add(employer)
        await session.flush()
        organization = await make_organization_for(session, employer)
        await session.commit()
        organization_id, user_id = organization.id, employer.id

    yield organization_id

    async with AsyncSession(test_engine) as session:
        await session.execute(
            text("UPDATE users SET organization_id = NULL WHERE id = :u"),
            {"u": user_id},
        )
        # Deleting the organization removes its balance and ledger rows (cascade).
        await session.execute(
            text("DELETE FROM organizations WHERE id = :o"), {"o": organization_id}
        )
        await session.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
        await session.commit()
