"""Integration tests for auth endpoints — full HTTP stack via test client."""

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_payload(**overrides) -> dict:
    """Return a valid registration JSON payload."""
    from tests.conftest import make_register_data
    data = make_register_data(**overrides)
    return {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
    }


async def register_and_get_tokens(client, **overrides) -> tuple[str, str, dict]:
    """Register a user and return (access_token, refresh_token_cookie, payload)."""
    payload = register_payload(**overrides)
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201
    access_token = reg.json()["access_token"]
    # httpx stores cookies on the client automatically after set-cookie headers
    refresh_token = reg.cookies.get("refresh_token")
    return access_token, refresh_token, payload


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_register_success(client):
    """POST /register returns 201 with access token, user info, and sets cookie."""
    payload = register_payload()
    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == payload["email"]
    # refresh token must be in cookie, not response body
    assert "refresh_token" not in body
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    """POST /register with a taken email returns 409."""
    payload = register_payload(email="dup@example.com", phone_number="08011111111")
    await client.post("/api/v1/auth/register", json=payload)

    payload2 = register_payload(email="dup@example.com", phone_number="08022222222")
    response = await client.post("/api/v1/auth/register", json=payload2)

    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_register_missing_field_returns_422(client):
    """POST /register without required fields returns 422 with field details."""
    response = await client.post("/api/v1/auth/register", json={"email": "x@x.com"})

    assert response.status_code == 422
    fields = [d["field"] for d in response.json()["details"]]
    assert "first_name" in fields


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success(client):
    """POST /login with valid credentials returns 200 with access token and sets cookie."""
    payload = register_payload()
    await client.post("/api/v1/auth/register", json=payload)

    response = await client.post("/api/v1/auth/login", json={
        "email": payload["email"],
        "password": payload["password"],
    })

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert "refresh_token" not in body
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    """POST /login with wrong password returns 401."""
    payload = register_payload()
    await client.post("/api/v1/auth/register", json=payload)

    response = await client.post("/api/v1/auth/login", json={
        "email": payload["email"],
        "password": "WrongPass99#",
    })

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(client):
    """POST /login with unknown email returns 401."""
    response = await client.post("/api/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "Password123#",
    })

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Protected route — /me
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_me_with_valid_token(client):
    """GET /me with a valid access token returns the user's profile."""
    access_token, _, payload = await register_and_get_tokens(client)

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    assert response.json()["email"] == payload["email"]


@pytest.mark.asyncio
async def test_get_me_without_token_returns_401(client):
    """GET /me with no token returns 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_wrong_role_returns_403(client):
    """A route requiring ADMIN role returns 403 for a GUEST user."""
    from fastapi import APIRouter, Depends

    from app.core.dependencies import require_role
    from app.main import app as fastapi_app

    access_token, _, _ = await register_and_get_tokens(client)

    test_router = APIRouter()

    @test_router.get("/test-admin-only")
    async def admin_only(user=Depends(require_role("ADMIN"))):
        return {"ok": True}

    fastapi_app.include_router(test_router, prefix="/api/v1")

    response = await client.get(
        "/api/v1/test-admin-only",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(client):
    """POST /refresh with a valid refresh cookie returns a new access token."""
    access_token, refresh_token, _ = await register_and_get_tokens(client)

    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    """POST /refresh with no cookie returns 401."""
    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 401
    assert response.json()["code"] == "REFRESH_TOKEN_MISSING"


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client):
    """POST /logout revokes the token — subsequent refresh returns 401."""
    access_token, refresh_token, _ = await register_and_get_tokens(client)

    logout = await client.post(
        "/api/v1/auth/logout",
        cookies={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout.status_code == 200

    # Refresh after logout must fail
    response = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": refresh_token},
    )
    assert response.status_code == 401
