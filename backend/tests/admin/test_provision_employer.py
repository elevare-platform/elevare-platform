"""An admin creates a client's account with a temporary password.

The client logs in, is forced to choose their own password, and their company
verification stays unapproved (documents are only needed to post a public job)."""

import pytest
from sqlalchemy import select

from app.modules.admin.models import AuditLog
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.auth.password_policy import must_change_password
from app.modules.auth.security import verify_password
from app.modules.users.models import Organization, User
from tests.conftest import make_admin, make_employer, make_user

URL = "/api/v1/admin/employers/provision"


def _body(**overrides):
    body = {
        "email": "samson@colton.example.com",
        "first_name": "Samson",
        "last_name": "Okafor",
        "phone_number": "+2348031234567",
        "company_name": "Colton Group",
    }
    body.update(overrides)
    return body


async def _admin_headers(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    token = create_token_pair(admin.id, admin.role)["access_token"]
    return admin, {"Authorization": f"Bearer {token}"}


async def _provision(client, db_session, **overrides):
    admin, headers = await _admin_headers(db_session)
    response = await client.post(URL, json=_body(**overrides), headers=headers)
    return admin, response


async def _user_by_email(db_session, email):
    return (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()


@pytest.mark.asyncio
async def test_provisioning_creates_the_account_and_company(client, db_session):
    _admin, response = await _provision(client, db_session)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "samson@colton.example.com"
    assert body["temporary_password"]

    user = await _user_by_email(db_session, "samson@colton.example.com")
    assert user.role == "EMPLOYER"
    assert user.account_status == "ACTIVE"
    assert user.email_verified is True
    assert user.organization_role == "OWNER"
    assert str(user.id) == body["user_id"]
    assert str(user.organization_id) == body["organization_id"]

    organization = await db_session.get(Organization, user.organization_id)
    assert organization.company_name == "Colton Group"
    assert organization.is_profile_complete is False
    # Documents are only needed to post a public job, so verification is left alone.
    assert organization.kyc_status == "NOT_SUBMITTED"


@pytest.mark.asyncio
async def test_the_password_is_stored_hashed_and_must_be_changed(client, db_session):
    _admin, response = await _provision(client, db_session)
    body = response.json()
    user = await _user_by_email(db_session, body["email"])

    assert user.password_hash != body["temporary_password"]
    assert verify_password(body["temporary_password"], user.password_hash)
    assert await must_change_password(db_session, user.id) is True


@pytest.mark.asyncio
async def test_the_client_can_log_in_but_must_change_the_password_first(
    client, db_session
):
    _admin, response = await _provision(client, db_session)
    body = response.json()

    login = await client.post(
        "/api/v1/auth/login",
        json={"email": body["email"], "password": body["temporary_password"]},
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    refused = await client.get("/api/v1/jobs/mine", headers=headers)
    assert refused.status_code == 403
    assert refused.json()["code"] == "PASSWORD_CHANGE_REQUIRED"

    new_password = "Colton-Own-Pass-9@"
    changed = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": body["temporary_password"],
            "new_password": new_password,
            "confirm_password": new_password,
        },
    )
    assert changed.status_code == 200
    ok = await client.get(
        "/api/v1/jobs/mine",
        headers={"Authorization": f"Bearer {changed.json()['access_token']}"},
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_the_password_is_never_written_to_the_audit_log(client, db_session):
    admin, response = await _provision(client, db_session)
    body = response.json()

    entries = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "PROVISION_EMPLOYER")
            )
        )
        .scalars()
        .all()
    )
    assert len(entries) == 1
    entry = entries[0]
    assert entry.admin_id == admin.id
    assert str(entry.target_id) == body["user_id"]
    assert entry.log_metadata["email"] == body["email"]
    assert entry.log_metadata["company_name"] == "Colton Group"
    assert body["temporary_password"] not in str(entry.log_metadata)
    assert "password" not in " ".join(entry.log_metadata).lower()


@pytest.mark.asyncio
async def test_the_response_must_not_be_cached(client, db_session):
    _admin, response = await _provision(client, db_session)

    assert "no-store" in response.headers["cache-control"]


@pytest.mark.asyncio
async def test_an_existing_email_is_refused_and_nothing_is_created(client, db_session):
    existing = make_employer(email="samson@colton.example.com")
    db_session.add(existing)
    await db_session.flush()

    _admin, response = await _provision(client, db_session)

    assert response.status_code == 409
    assert "temporary_password" not in response.text
    entries = (
        (
            await db_session.execute(
                select(AuditLog).where(AuditLog.action == "PROVISION_EMPLOYER")
            )
        )
        .scalars()
        .all()
    )
    assert entries == []


@pytest.mark.asyncio
async def test_an_existing_phone_number_is_refused(client, db_session):
    existing = make_employer(phone_number="+2348031234567")
    db_session.add(existing)
    await db_session.flush()

    _admin, response = await _provision(client, db_session)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_a_phone_number_is_optional(client, db_session):
    _admin, response = await _provision(client, db_session, phone_number=None)

    assert response.status_code == 201
    user = await _user_by_email(db_session, "samson@colton.example.com")
    assert user.phone_number is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "not-an-email"},
        {"company_name": ""},
        {"first_name": ""},
        {"first_name": "A" * 31},  # the database column holds 30 characters
        {"last_name": "B" * 31},
        {"phone_number": "12345"},
    ],
)
async def test_bad_input_is_a_422(client, db_session, overrides):
    _admin, response = await _provision(client, db_session, **overrides)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_only_an_admin_can_provision(client, db_session):
    employer = make_employer()
    candidate = make_user(role="CANDIDATE")
    db_session.add_all([employer, candidate])
    await db_session.flush()

    for user in (employer, candidate):
        token = create_token_pair(user.id, user.role)["access_token"]
        response = await client.post(
            URL, json=_body(), headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    anonymous = await client.post(URL, json=_body())
    assert anonymous.status_code == 401
