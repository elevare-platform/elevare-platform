"""Tests for AuthRepository — direct DB operations, no HTTP."""

from datetime import UTC

import pytest

from app.core.exceptions import TokenInvalidException
from app.modules.auth.repository import AuthRepository
from app.modules.auth.security import hash_token


@pytest.mark.asyncio
async def test_create_refresh_token(db_session):
    """create_refresh_token stores a hashed token linked to the user."""
    from tests.conftest import future, make_user

    user = make_user()
    db_session.add(user)
    await db_session.flush()

    raw_token = "raw_jwt_string"
    repo = AuthRepository(db_session)
    record = await repo.create_refresh_token(
        user_id=user.id,
        raw_token=raw_token,
        expires_at=future(minutes=60 * 24 * 30),
    )

    assert record.id is not None
    assert record.user_id == user.id
    assert record.token == hash_token(raw_token)  # hash stored, not plaintext
    assert record.token != raw_token
    assert record.is_revoked is False
    assert record.used_at is None


@pytest.mark.asyncio
async def test_get_refresh_token_by_raw_value(db_session):
    """get_refresh_token looks up by raw token and returns the record."""
    from tests.conftest import future, make_user

    user = make_user()
    db_session.add(user)
    await db_session.flush()

    raw_token = "lookup_test_token"
    repo = AuthRepository(db_session)
    await repo.create_refresh_token(user.id, raw_token, future(minutes=60))

    found = await repo.get_refresh_token(raw_token)

    assert found is not None
    assert found.user_id == user.id
    assert found.token == hash_token(raw_token)


@pytest.mark.asyncio
async def test_get_refresh_token_returns_none_for_unknown(db_session):
    """get_refresh_token returns None when the token doesn't exist."""
    repo = AuthRepository(db_session)
    result = await repo.get_refresh_token("nonexistent_token")
    assert result is None


@pytest.mark.asyncio
async def test_revoke_refresh_token(db_session):
    """revoke_refresh_token sets is_revoked=True and records used_at."""
    from tests.conftest import future, make_user

    user = make_user()
    db_session.add(user)
    await db_session.flush()

    raw_token = "token_to_revoke"
    repo = AuthRepository(db_session)
    await repo.create_refresh_token(user.id, raw_token, future(minutes=60))

    await repo.revoke_refresh_token(raw_token)

    record = await repo.get_refresh_token(raw_token)
    assert record.is_revoked is True
    assert record.used_at is not None
    assert record.used_at.tzinfo == UTC


@pytest.mark.asyncio
async def test_revoke_nonexistent_token_raises(db_session):
    """revoke_refresh_token raises TokenInvalidException for unknown tokens."""
    repo = AuthRepository(db_session)

    with pytest.raises(TokenInvalidException):
        await repo.revoke_refresh_token("ghost_token")
