"""Tests for the admin invite flow.

Covers:
- Admin creates invite → token returned
- Invite accept with valid token → account ACTIVE, tokens returned
- Invite accept with expired token → correct error
- Invite accept with already-used token → correct error
- Invite accept with unknown token → correct error
- Non-admin cannot create invite
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Response

from app.core.exceptions import VerificationTokenExpiredException
from app.modules.auth.models import InviteToken
from app.modules.auth.security import generate_token, hash_token
from app.modules.auth.service import AuthService
from app.modules.users.enums import AccountStatus, UserRole


def mock_response() -> Response:
    """Return a mock FastAPI Response object for use in service-layer tests."""
    return MagicMock(spec=Response)


def accept_payload(**overrides) -> dict:
    """Valid accept-invite request body."""
    from uuid import uuid4

    defaults = {
        "first_name": "Tunde",
        "last_name": "Bakare",
        "phone_number": f"0801{uuid4().int % 10**7:07d}",
        "password": "Secure123#",
        "confirm_password": "Secure123#",
    }
    defaults.update(overrides)
    return defaults


async def get_admin_token(client, db_session) -> str:
    """Register a user and promote to ADMIN. Returns access token."""
    from sqlalchemy import select

    from app.modules.users.models import User
    from tests.conftest import make_register_data

    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = "ADMIN"
    user.account_status = "ACTIVE"
    user.email_verified = True
    await db_session.flush()

    from app.modules.auth.jwt_handler import create_token_pair

    token_pair = create_token_pair(user.id, "ADMIN")
    return token_pair["access_token"]


# ---------------------------------------------------------------------------
# Admin creates invite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_create_invite_returns_token(client, db_session):
    """POST /admin/employers/invite returns invite_token in stub mode."""
    admin_token = await get_admin_token(client, db_session)

    response = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": f"employer_{uuid4().hex[:6]}@company.com", "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert "invite_token" in response.json()
    assert response.json()["invite_token"]


@pytest.mark.asyncio
async def test_non_admin_cannot_create_invite(client, db_session):
    """POST /admin/employers/invite returns 403 for non-admin users."""
    from sqlalchemy import select

    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import User
    from tests.conftest import make_register_data

    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    # Promote to EMPLOYER (not ADMIN) and activate
    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = "EMPLOYER"
    user.account_status = "ACTIVE"
    await db_session.flush()

    token_pair = create_token_pair(user.id, "EMPLOYER")
    employer_token = token_pair["access_token"]

    response = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": "someone@company.com", "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_invite_duplicate_email_returns_409(client, db_session):
    """POST /admin/employers/invite with existing email returns 409."""
    admin_token = await get_admin_token(client, db_session)
    email = f"taken_{uuid4().hex[:6]}@company.com"

    # First invite
    r1 = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 200

    # Second invite — same email, but no user created yet so this tests
    # the service-level duplicate check on the invite itself.
    # Actually the service checks the users table, not invite_tokens.
    # So a second invite to the same email (no user yet) should succeed.
    # Only fails if a user with that email already exists.
    # Let's test with an email that already has a registered user.
    from tests.conftest import make_register_data

    data = make_register_data()
    reg_payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    await client.post("/api/v1/auth/register", json=reg_payload)

    response = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": data.email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_EXISTS"


# ---------------------------------------------------------------------------
# Accept invite — valid token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_invite_valid_token_returns_auth_response(client, db_session):
    """POST /auth/invite/accept with valid token creates user and returns tokens."""
    admin_token = await get_admin_token(client, db_session)
    email = f"newemployer_{uuid4().hex[:6]}@company.com"

    # Admin creates invite
    invite_resp = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_resp.status_code == 200
    invite_token = invite_resp.json()["invite_token"]

    # Employer accepts invite
    response = await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": invite_token},
        json=accept_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == email
    assert body["user"]["account_status"] == "ACTIVE"
    assert response.cookies.get("refresh_token")


@pytest.mark.asyncio
async def test_accept_invite_account_is_active_and_verified(client, db_session):
    """Accepted invite sets account_status ACTIVE and email_verified True."""
    from sqlalchemy import select

    from app.modules.users.models import User

    admin_token = await get_admin_token(client, db_session)
    email = f"verified_{uuid4().hex[:6]}@company.com"

    invite_resp = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    invite_token = invite_resp.json()["invite_token"]

    await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": invite_token},
        json=accept_payload(),
    )

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()

    assert user.account_status == AccountStatus.ACTIVE.value
    assert user.email_verified is True
    assert user.email_verified_at is not None


# ---------------------------------------------------------------------------
# Accept invite — error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_invite_unknown_token_returns_401(client):
    """POST /auth/invite/accept with unknown token returns 401 TOKEN_INVALID."""
    response = await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": "completely_fake_token_xyz"},
        json=accept_payload(),
    )
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


@pytest.mark.asyncio
async def test_accept_invite_expired_token_returns_400(db_session):
    """Service raises VerificationTokenExpiredException for expired invite token."""
    from tests.conftest import make_user

    admin = make_user(role="ADMIN", account_status="ACTIVE")
    db_session.add(admin)
    await db_session.flush()

    # Plant an expired invite token directly
    raw_token = generate_token()
    hashed = hash_token(raw_token)
    expired_invite = InviteToken(
        email=f"expired_{uuid4().hex[:6]}@company.com",
        token=hashed,
        role=UserRole.EMPLOYER.value,
        expires_at=datetime.now(UTC) - timedelta(days=1),  # expired yesterday
        is_used=False,
        invited_by=admin.id,
    )
    db_session.add(expired_invite)
    await db_session.flush()

    from uuid import uuid4 as u4

    from app.modules.auth.schemas import AcceptInviteRequest

    data = AcceptInviteRequest(
        first_name="Test",
        last_name="User",
        phone_number=f"0801{u4().int % 10**7:07d}",
        password="Secure123#",
        confirm_password="Secure123#",
    )

    service = AuthService(db_session)
    with pytest.raises(VerificationTokenExpiredException):
        await service.accept_invite(raw_token, data, mock_response())


@pytest.mark.asyncio
async def test_accept_invite_already_used_token_returns_400(client, db_session):
    """POST /auth/invite/accept with already-used token returns 400 TOKEN_ALREADY_USED."""
    admin_token = await get_admin_token(client, db_session)
    email = f"once_{uuid4().hex[:6]}@company.com"

    invite_resp = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    invite_token = invite_resp.json()["invite_token"]

    # Accept once — valid
    first = await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": invite_token},
        json=accept_payload(),
    )
    assert first.status_code == 200

    # Accept again — token already used
    second = await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": invite_token},
        json=accept_payload(),
    )
    assert second.status_code == 400
    assert second.json()["code"] == "TOKEN_ALREADY_USED"


# ---------------------------------------------------------------------------
# Resend invite
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resend_invite_returns_new_token(client, db_session):
    """POST /admin/employers/invite/{token}/resend returns a new invite token."""
    admin_token = await get_admin_token(client, db_session)
    email = f"resend_{uuid4().hex[:6]}@company.com"

    # Create initial invite
    invite_resp = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    original_token = invite_resp.json()["invite_token"]

    # Resend
    resend_resp = await client.post(
        f"/api/v1/admin/employers/invite/{original_token}/resend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resend_resp.status_code == 200
    new_token = resend_resp.json()["invite_token"]
    assert new_token != original_token


@pytest.mark.asyncio
async def test_resend_invite_old_token_no_longer_valid(client, db_session):
    """After resend, the original invite token is invalidated."""
    admin_token = await get_admin_token(client, db_session)
    email = f"invalidate_{uuid4().hex[:6]}@company.com"

    invite_resp = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    original_token = invite_resp.json()["invite_token"]

    # Resend — invalidates original
    await client.post(
        f"/api/v1/admin/employers/invite/{original_token}/resend",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Try to accept with the original token — should fail
    response = await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": original_token},
        json=accept_payload(),
    )
    assert response.status_code == 400
    assert response.json()["code"] == "TOKEN_ALREADY_USED"


# ---------------------------------------------------------------------------
# Invite acceptance collision — email already registered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_accept_invite_collision_with_existing_user_returns_409(
    client, db_session
):
    """POST /auth/invite/accept returns 409 if the invited email already has an account.

    Scenario: admin invites email X, then someone registers with email X before
    the invite is accepted. Acceptance must fail loudly, not silently upgrade.
    """
    from tests.conftest import make_register_data

    admin_token = await get_admin_token(client, db_session)
    email = f"collision_{uuid4().hex[:6]}@company.com"

    # Admin creates invite for this email
    invite_resp = await client.post(
        "/api/v1/admin/employers/invite",
        json={"email": email, "role": "EMPLOYER"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert invite_resp.status_code == 200
    invite_token = invite_resp.json()["invite_token"]

    # Someone registers with the same email before the invite is accepted
    data = make_register_data(email=email)
    reg_payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg.status_code == 201

    # Now try to accept the invite — should fail with 409
    response = await client.post(
        "/api/v1/auth/invite/accept",
        params={"token": invite_token},
        json=accept_payload(),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_EXISTS"
