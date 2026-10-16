"""An account provisioned with a temporary password must set its own before doing
anything else. The server enforces it: a refused request, not a hidden screen."""

import pytest
from sqlalchemy import select

from app.modules.auth.models import RefreshToken
from app.modules.auth.password_policy import (
    must_change_password,
    set_must_change_password,
)
from app.modules.auth.security import hash_password
from tests.conftest import make_employer

TEMP_PASSWORD = "Temp-Pass-1!"
NEW_PASSWORD = "Brand-New-Pass-2@"


async def _provisioned_employer(db_session, must_change=True, **overrides):
    employer = make_employer(password_hash=hash_password(TEMP_PASSWORD), **overrides)
    db_session.add(employer)
    await db_session.flush()
    if must_change:
        await set_must_change_password(db_session, employer.id, True)
    return employer


async def _login(client, employer, password=TEMP_PASSWORD):
    return await client.post(
        "/api/v1/auth/login", json={"email": employer.email, "password": password}
    )


def _bearer(login_response) -> dict:
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_login_reports_that_a_password_change_is_required(client, db_session):
    employer = await _provisioned_employer(db_session)

    response = await _login(client, employer)

    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


@pytest.mark.asyncio
async def test_login_for_an_ordinary_user_does_not_ask_for_a_change(client, db_session):
    employer = await _provisioned_employer(db_session, must_change=False)

    response = await _login(client, employer)

    assert response.json()["must_change_password"] is False
    ok = await client.get("/api/v1/jobs/mine", headers=_bearer(response))
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_a_marked_token_is_refused_on_ordinary_endpoints(client, db_session):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)

    response = await client.get("/api/v1/jobs/mine", headers=_bearer(login))

    assert response.status_code == 403
    assert response.json()["code"] == "PASSWORD_CHANGE_REQUIRED"


@pytest.mark.asyncio
async def test_a_marked_token_can_still_read_me_and_says_why(client, db_session):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)

    response = await client.get("/api/v1/auth/me", headers=_bearer(login))

    assert response.status_code == 200
    assert response.json()["must_change_password"] is True


@pytest.mark.asyncio
async def test_refreshing_keeps_the_mark(client, db_session):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)
    refresh_cookie = login.cookies.get("refresh_token")

    refreshed = await client.post(
        "/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie}
    )
    assert refreshed.status_code == 200

    response = await client.get(
        "/api/v1/jobs/mine",
        headers={"Authorization": f"Bearer {refreshed.json()['access_token']}"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "PASSWORD_CHANGE_REQUIRED"


@pytest.mark.asyncio
async def test_a_marked_token_is_treated_as_anonymous_on_public_pages(
    client, db_session
):
    """get_optional_user would otherwise recognise the user, and a public page
    can show an owner things (such as an unpublished job) that an anonymous
    visitor does not see."""
    from app.core.dependencies import get_optional_user
    from app.modules.auth.jwt_handler import create_token_pair

    employer = await _provisioned_employer(db_session)
    marked = create_token_pair(employer.id, employer.role, must_change_password=True)
    plain = create_token_pair(employer.id, employer.role)

    assert await get_optional_user(marked["access_token"], db_session) is None
    assert (
        await get_optional_user(plain["access_token"], db_session)
    ).id == employer.id


@pytest.mark.asyncio
async def test_a_marked_token_can_log_out(client, db_session):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)

    response = await client.post(
        "/api/v1/auth/logout",
        headers=_bearer(login),
        cookies={"refresh_token": login.cookies.get("refresh_token")},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_change_password_success_clears_the_flag_and_logs_in_again(
    client, db_session
):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)

    response = await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(login),
        json={
            "current_password": TEMP_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert response.json()["must_change_password"] is False
    assert await must_change_password(db_session, employer.id) is False
    # The fresh token works everywhere straight away.
    ok = await client.get("/api/v1/jobs/mine", headers=_bearer(response))
    assert ok.status_code == 200
    # The temporary password is dead; the new one logs in without a flag.
    assert (await _login(client, employer, TEMP_PASSWORD)).status_code == 401
    relogin = await _login(client, employer, NEW_PASSWORD)
    assert relogin.status_code == 200
    assert relogin.json()["must_change_password"] is False


@pytest.mark.asyncio
async def test_changing_the_password_revokes_the_older_sessions(client, db_session):
    employer = await _provisioned_employer(db_session)
    first = await _login(client, employer)
    second = await _login(client, employer)

    await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(first),
        json={
            "current_password": TEMP_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    # Every refresh token issued before the change is revoked; only the one the
    # change itself issued is still usable.
    rows = (
        (
            await db_session.execute(
                select(RefreshToken).where(RefreshToken.user_id == employer.id)
            )
        )
        .scalars()
        .all()
    )
    assert sum(1 for row in rows if not row.is_revoked) == 1
    stale = await client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": second.cookies.get("refresh_token")},
    )
    assert stale.status_code in (401, 403)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("current", "new", "confirm", "expected_status"),
    [
        # A wrong current password is a 400, never a 401 (which the frontend reads
        # as an expired session).
        ("not-the-password", NEW_PASSWORD, NEW_PASSWORD, 400),
        (TEMP_PASSWORD, "weak", "weak", 422),  # fails the strength rules
        (TEMP_PASSWORD, NEW_PASSWORD, "Different-Pass-3#", 422),  # confirmation differs
        (TEMP_PASSWORD, TEMP_PASSWORD, TEMP_PASSWORD, 422),  # the same password again
    ],
)
async def test_change_password_refuses_bad_input(
    client, db_session, current, new, confirm, expected_status
):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)

    response = await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(login),
        json={
            "current_password": current,
            "new_password": new,
            "confirm_password": confirm,
        },
    )

    assert response.status_code == expected_status
    assert await must_change_password(db_session, employer.id) is True


@pytest.mark.asyncio
async def test_change_password_needs_a_logged_in_user(client):
    response = await client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": TEMP_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_a_suspended_user_cannot_change_their_password(client, db_session):
    employer = await _provisioned_employer(db_session)
    login = await _login(client, employer)
    # Through the object, not raw SQL: the API shares this test's session, which
    # already holds the user.
    employer.account_status = "SUSPENDED"
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(login),
        json={
            "current_password": TEMP_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "ACCOUNT_SUSPENDED"


@pytest.mark.asyncio
async def test_an_ordinary_user_can_change_their_password_too(client, db_session):
    employer = await _provisioned_employer(db_session, must_change=False)
    login = await _login(client, employer)

    response = await client.post(
        "/api/v1/auth/change-password",
        headers=_bearer(login),
        json={
            "current_password": TEMP_PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    assert response.status_code == 200
    assert (await _login(client, employer, NEW_PASSWORD)).status_code == 200
