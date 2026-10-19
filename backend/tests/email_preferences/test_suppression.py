"""suppressed_addresses: the lookup the email sender makes, with its own connection.

It opens a separate connection, so these tests use rows that are really committed (the
usual rolled-back test session would be invisible to it) and remove them afterwards."""

import uuid
from types import SimpleNamespace

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_preferences import suppression
from app.modules.email_preferences.suppression import suppressed_addresses
from tests.conftest import test_engine

PREFIX = f"suppression-test-{uuid.uuid4().hex[:8]}"
OFF = f"{PREFIX}-off@example.com"
ON = f"{PREFIX}-on@example.com"


@pytest_asyncio.fixture
async def one_address_off():
    async with AsyncSession(test_engine) as session:
        await session.execute(
            text(
                "INSERT INTO email_suppressions (id, email, source) "
                "VALUES (:id, :email, 'SETTINGS')"
            ),
            {"id": uuid.uuid4(), "email": OFF},
        )
        await session.commit()

    yield

    async with AsyncSession(test_engine) as session:
        await session.execute(
            text("DELETE FROM email_suppressions WHERE email LIKE :p"),
            {"p": f"{PREFIX}%"},
        )
        await session.commit()


@pytest.mark.asyncio
async def test_it_returns_only_the_addresses_that_turned_emails_off(one_address_off):
    assert await suppressed_addresses([OFF, ON]) == {OFF}


@pytest.mark.asyncio
async def test_it_matches_whatever_the_case_of_the_recipient(one_address_off):
    assert await suppressed_addresses([OFF.upper()]) == {OFF}


@pytest.mark.asyncio
async def test_nobody_listed_is_an_empty_answer_without_touching_the_database(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("no connection should be opened")

    monkeypatch.setattr(suppression, "create_async_engine", boom)

    assert await suppressed_addresses([]) == set()


# --- the deploy gap: the code may run before the migration has created the table ----------


class _FailingEngine:
    """An engine whose queries fail with the given database error."""

    def __init__(self, error):
        self._error = error
        self.disposed = False

    def connect(self):
        raise self._error

    async def dispose(self):
        self.disposed = True


def _database_error(sqlstate):
    original = SimpleNamespace(sqlstate=sqlstate)
    return ProgrammingError("SELECT ...", {}, original)


@pytest.mark.asyncio
async def test_a_missing_table_means_nobody_has_unsubscribed_yet(monkeypatch, caplog):
    engine = _FailingEngine(_database_error("42P01"))
    monkeypatch.setattr(suppression, "create_async_engine", lambda *a, **k: engine)

    with caplog.at_level("WARNING"):
        result = await suppressed_addresses(["ada@example.com"])

    assert result == set()
    assert "table is missing" in caplog.text
    assert engine.disposed


@pytest.mark.asyncio
async def test_any_other_database_error_is_raised_not_hidden(monkeypatch):
    engine = _FailingEngine(_database_error("42703"))  # a missing column, say
    monkeypatch.setattr(suppression, "create_async_engine", lambda *a, **k: engine)

    with pytest.raises(ProgrammingError):
        await suppressed_addresses(["ada@example.com"])
    assert engine.disposed
