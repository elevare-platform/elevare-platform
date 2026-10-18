"""The must-change-password flag: stored per user, and safe while the column is
still being added by a migration that runs after the new containers are up."""

import pytest
from sqlalchemy import text

from app.modules.auth.password_policy import (
    must_change_password,
    set_must_change_password,
)
from tests.conftest import make_employer


async def _saved_user(db_session):
    user = make_employer()
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_a_new_user_does_not_have_to_change_their_password(db_session):
    user = await _saved_user(db_session)

    assert await must_change_password(db_session, user.id) is False


@pytest.mark.asyncio
async def test_the_flag_can_be_set_and_cleared(db_session):
    user = await _saved_user(db_session)

    await set_must_change_password(db_session, user.id, True)
    assert await must_change_password(db_session, user.id) is True

    await set_must_change_password(db_session, user.id, False)
    assert await must_change_password(db_session, user.id) is False


@pytest.mark.asyncio
async def test_setting_the_flag_for_one_user_leaves_others_alone(db_session):
    first = await _saved_user(db_session)
    second = await _saved_user(db_session)

    await set_must_change_password(db_session, first.id, True)

    assert await must_change_password(db_session, second.id) is False


@pytest.mark.asyncio
async def test_an_unknown_user_does_not_have_to_change_anything(db_session):
    from uuid import uuid4

    assert await must_change_password(db_session, uuid4()) is False


@pytest.mark.asyncio
async def test_reading_the_flag_survives_a_column_that_does_not_exist_yet(db_session):
    """For the seconds between the new containers starting and the migration
    finishing, the column is missing. Every login would fail if reading it raised.
    (The DDL is undone when the test's transaction rolls back.)"""
    user = await _saved_user(db_session)
    await db_session.execute(text("ALTER TABLE users DROP COLUMN must_change_password"))

    assert await must_change_password(db_session, user.id) is False

    # The caller's transaction is still usable afterwards.
    assert (await db_session.execute(text("SELECT 1"))).scalar_one() == 1
