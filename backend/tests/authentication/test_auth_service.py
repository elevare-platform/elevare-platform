"""Tests for AuthService — business logic layer, no HTTP."""

from unittest.mock import MagicMock

import pytest
from fastapi import Response

from app.core.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
    RevokedTokenException,
)
from app.modules.auth.schemas import LoginRequest
from app.modules.auth.service import AuthService


def mock_response() -> Response:
    """Return a mock FastAPI Response object for service tests."""
    return MagicMock(spec=Response)


@pytest.mark.asyncio
async def test_register_returns_auth_response(db_session):
    """Successful registration returns access token and user info."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    response = await service.register_user(make_register_data(), mock_response())

    assert response.access_token
    assert response.token_type == "bearer"
    assert response.user.email


@pytest.mark.asyncio
async def test_register_raises_on_duplicate_email(db_session):
    """Registering with an already-taken email raises AlreadyExistsException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    # First registration — unique email, random phone
    data = make_register_data(email="unique_taken@example.com")
    await service.register_user(data, mock_response())

    # Second registration — same email, different random phone
    with pytest.raises(AlreadyExistsException) as exc_info:
        await service.register_user(
            make_register_data(email="unique_taken@example.com"),
            mock_response(),
        )
    # Confirm it failed on email, not phone
    assert "email" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_login_returns_auth_response(db_session):
    """Valid credentials return access token and user info."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    await service.register_user(data, mock_response())

    response = await service.login_user(
        LoginRequest(email=data.email, password=data.password),
        mock_response(),
    )

    assert response.access_token
    assert response.user.email == data.email


@pytest.mark.asyncio
async def test_login_raises_on_wrong_password(db_session):
    """Wrong password raises InvalidCredentialsException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    await service.register_user(data, mock_response())

    with pytest.raises(InvalidCredentialsException):
        await service.login_user(
            LoginRequest(email=data.email, password="WrongPass1#"),
            mock_response(),
        )


@pytest.mark.asyncio
async def test_login_raises_on_unknown_email(db_session):
    """Unknown email raises InvalidCredentialsException."""
    service = AuthService(db_session)

    with pytest.raises(InvalidCredentialsException):
        await service.login_user(
            LoginRequest(email="ghost@example.com", password="Password123#"),
            mock_response(),
        )


@pytest.mark.asyncio
async def test_refresh_access_token_returns_new_token(db_session):
    """Valid refresh token returns a new access token."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()

    # Capture the refresh token from the mock response cookie call
    resp = MagicMock(spec=Response)
    await service.register_user(data, resp)

    # Extract the refresh token value from the set_cookie call
    _, kwargs = resp.set_cookie.call_args
    refresh_token = kwargs["value"]

    result = await service.refresh_access_token(refresh_token)

    assert result["access_token"]
    assert result["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_revoke_refresh_token(db_session):
    """After logout, revoking the same token again raises RevokedTokenException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    resp = MagicMock(spec=Response)
    await service.register_user(data, resp)

    _, kwargs = resp.set_cookie.call_args
    refresh_token = kwargs["value"]

    await service.revoke_refresh_token(refresh_token)

    with pytest.raises(RevokedTokenException):
        await service.revoke_refresh_token(refresh_token)


@pytest.mark.asyncio
async def test_refresh_raises_on_revoked_token(db_session):
    """Refreshing with a revoked token raises RevokedTokenException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    resp = MagicMock(spec=Response)
    await service.register_user(data, resp)

    _, kwargs = resp.set_cookie.call_args
    refresh_token = kwargs["value"]

    await service.revoke_refresh_token(refresh_token)

    with pytest.raises(RevokedTokenException):
        await service.refresh_access_token(refresh_token)
