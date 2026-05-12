"""Tests for AuthService — business logic layer, no HTTP."""

import pytest

from app.core.exceptions import (
    AlreadyExistsException,
    InvalidCredentialsException,
    RevokedTokenException,
)
from app.modules.auth.service import AuthService


@pytest.mark.asyncio
async def test_register_returns_auth_response(db_session):
    """Successful registration returns tokens and user info."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    response = await service.register_user(make_register_data())

    assert response.access_token
    assert response.refresh_token
    assert response.token_type == "bearer"
    assert response.user.email


@pytest.mark.asyncio
async def test_register_raises_on_duplicate_email(db_session):
    """Registering with an already-taken email raises AlreadyExistsException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data(email="taken@example.com", phone_number="08011111111")
    await service.register_user(data)

    with pytest.raises(AlreadyExistsException):
        await service.register_user(
            make_register_data(email="taken@example.com", phone_number="08022222222")
        )


@pytest.mark.asyncio
async def test_login_returns_auth_response(db_session):
    """Valid credentials return tokens and user info."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    await service.register_user(data)

    response = await service.login_user(
        type("LoginRequest", (), {"email": data.email, "password": data.password})()
    )

    assert response.access_token
    assert response.refresh_token
    assert response.user.email == data.email


@pytest.mark.asyncio
async def test_login_raises_on_wrong_password(db_session):
    """Wrong password raises InvalidCredentialsException."""
    from app.modules.auth.schemas import LoginRequest
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    await service.register_user(data)

    with pytest.raises(InvalidCredentialsException):
        await service.login_user(LoginRequest(email=data.email, password="WrongPass1#"))


@pytest.mark.asyncio
async def test_login_raises_on_unknown_email(db_session):
    """Unknown email raises InvalidCredentialsException (same error as wrong password)."""
    from app.modules.auth.schemas import LoginRequest

    service = AuthService(db_session)

    with pytest.raises(InvalidCredentialsException):
        await service.login_user(
            LoginRequest(email="ghost@example.com", password="Password123#")
        )


@pytest.mark.asyncio
async def test_refresh_access_token_returns_new_token(db_session):
    """Valid refresh token returns a new access token."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    registered = await service.register_user(data)

    result = await service.refresh_access_token(registered.refresh_token)

    assert result["access_token"]
    assert result["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_revoke_refresh_token(db_session):
    """After logout, using the refresh token raises RevokedTokenException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    registered = await service.register_user(data)

    await service.revoke_refresh_token(registered.refresh_token)

    with pytest.raises(RevokedTokenException):
        await service.revoke_refresh_token(registered.refresh_token)


@pytest.mark.asyncio
async def test_refresh_raises_on_revoked_token(db_session):
    """Refreshing with a revoked token raises RevokedTokenException."""
    from tests.conftest import make_register_data

    service = AuthService(db_session)
    data = make_register_data()
    registered = await service.register_user(data)

    await service.revoke_refresh_token(registered.refresh_token)

    with pytest.raises(RevokedTokenException):
        await service.refresh_access_token(registered.refresh_token)
