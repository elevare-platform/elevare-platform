"""Tests for account status enforcement in get_current_user.

Every protected endpoint inherits this behaviour. These tests verify that
users with non-ACTIVE account statuses are blocked with 403.
"""

import pytest

from app.modules.auth.jwt_handler import create_token_pair


def make_token(user) -> str:
    """Generate a valid JWT for a user regardless of their account status."""
    token_pair = create_token_pair(user.id, user.role)
    return token_pair["access_token"]


@pytest.mark.asyncio
async def test_pending_verification_blocked(client, db_session):
    """User with PENDING_VERIFICATION status cannot access protected endpoints."""
    from tests.conftest import make_user

    user = make_user(account_status="PENDING_VERIFICATION")
    db_session.add(user)
    await db_session.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {make_token(user)}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "EMAIL_VERIFICATION_REQUIRED"


@pytest.mark.asyncio
async def test_invited_blocked(client, db_session):
    """User with INVITED status cannot access protected endpoints."""
    from tests.conftest import make_user

    user = make_user(account_status="INVITED")
    db_session.add(user)
    await db_session.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {make_token(user)}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_SETUP_INCOMPLETE"


@pytest.mark.asyncio
async def test_suspended_blocked(client, db_session):
    """User with SUSPENDED status cannot access protected endpoints."""
    from tests.conftest import make_user

    user = make_user(account_status="SUSPENDED")
    db_session.add(user)
    await db_session.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {make_token(user)}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_SUSPENDED"


@pytest.mark.asyncio
async def test_banned_blocked(client, db_session):
    """User with BANNED status cannot access protected endpoints."""
    from tests.conftest import make_user

    user = make_user(account_status="BANNED")
    db_session.add(user)
    await db_session.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {make_token(user)}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_BANNED"


@pytest.mark.asyncio
async def test_deactivated_blocked(client, db_session):
    """User with DEACTIVATED status cannot access protected endpoints."""
    from tests.conftest import make_user

    user = make_user(account_status="DEACTIVATED")
    db_session.add(user)
    await db_session.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {make_token(user)}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_DEACTIVATED"


@pytest.mark.asyncio
async def test_active_user_allowed(client, db_session):
    """User with ACTIVE status can access protected endpoints."""
    from tests.conftest import make_user

    user = make_user()
    db_session.add(user)
    await db_session.flush()

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {make_token(user)}"},
    )
    assert response.status_code == 200
