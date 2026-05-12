"""Tests for ORM model behaviour — no HTTP, no service layer."""

import pytest

from app.modules.auth.models import RefreshToken
from app.modules.auth.security import hash_token


@pytest.mark.asyncio
async def test_refresh_token_stores_hash(db_session):
    """Stored token value must be the sha256 hash, never the raw string."""
    from tests.conftest import future, make_user

    user = make_user()
    db_session.add(user)
    await db_session.flush()

    raw_token = "sample_token_string"
    hashed = hash_token(raw_token)

    refresh_token = RefreshToken(
        user_id=user.id,
        token=hashed,
        expires_at=future(minutes=30),
        is_revoked=False,
    )
    db_session.add(refresh_token)
    await db_session.flush()

    assert refresh_token.id is not None
    assert refresh_token.user_id == user.id
    assert refresh_token.used_at is None
    assert refresh_token.token == hash_token(raw_token)
    assert refresh_token.token != raw_token  # plaintext must never be stored
