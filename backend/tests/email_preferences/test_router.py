"""The unsubscribe and email-preference endpoints."""

import pytest
from sqlalchemy import select

from app.modules.email_preferences.models import EmailSuppression
from app.modules.email_preferences.tokens import make_unsubscribe_token
from tests.interviews.test_interview_router import register_and_promote

BASE = "/api/v1/email-preferences"
ADDRESS = "ada.lovelace@example.com"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def rows(db_session, email: str) -> list[EmailSuppression]:
    return list(
        (
            await db_session.execute(
                select(EmailSuppression).where(EmailSuppression.email == email)
            )
        )
        .scalars()
        .all()
    )


# --- from the link in an email (no login) -------------------------------------------------


@pytest.mark.asyncio
async def test_opening_the_page_only_shows_it_and_changes_nothing(client, db_session):
    """Email security scanners open every link: a link that unsubscribed on open
    would unsubscribe people who never asked."""
    token = make_unsubscribe_token(ADDRESS)

    first = await client.get(f"{BASE}/unsubscribe", params={"token": token})
    second = await client.get(f"{BASE}/unsubscribe", params={"token": token})

    assert first.status_code == 200
    assert first.json() == {"email": "a***@example.com", "emails_enabled": True}
    assert second.json()["emails_enabled"] is True
    assert await rows(db_session, ADDRESS) == []


@pytest.mark.asyncio
async def test_confirming_turns_emails_off_for_that_address(client, db_session):
    token = make_unsubscribe_token(ADDRESS)

    resp = await client.post(f"{BASE}/unsubscribe", params={"token": token})

    assert resp.status_code == 200
    assert resp.json() == {"email": "a***@example.com", "emails_enabled": False}
    [row] = await rows(db_session, ADDRESS)
    assert row.source == "EMAIL_LINK"
    # The page now reflects it.
    preview = await client.get(f"{BASE}/unsubscribe", params={"token": token})
    assert preview.json()["emails_enabled"] is False


@pytest.mark.asyncio
async def test_a_mail_clients_one_click_post_works_like_confirming(client, db_session):
    """RFC 8058: Gmail and others POST `List-Unsubscribe=One-Click` as a form to the
    URL in the List-Unsubscribe header."""
    token = make_unsubscribe_token(ADDRESS)

    resp = await client.post(
        f"{BASE}/unsubscribe",
        params={"token": token},
        data={"List-Unsubscribe": "One-Click"},
    )

    assert resp.status_code == 200
    assert len(await rows(db_session, ADDRESS)) == 1


@pytest.mark.asyncio
async def test_unsubscribing_twice_is_harmless(client, db_session):
    token = make_unsubscribe_token(ADDRESS)

    first = await client.post(f"{BASE}/unsubscribe", params={"token": token})
    second = await client.post(f"{BASE}/unsubscribe", params={"token": token})

    assert (first.status_code, second.status_code) == (200, 200)
    assert len(await rows(db_session, ADDRESS)) == 1


@pytest.mark.asyncio
async def test_a_link_only_affects_the_address_it_was_made_for(client, db_session):
    await client.post(f"{BASE}/unsubscribe", params={"token": make_unsubscribe_token(ADDRESS)})

    assert await rows(db_session, "someone.else@example.com") == []


@pytest.mark.asyncio
async def test_changing_your_mind_turns_emails_back_on(client, db_session):
    token = make_unsubscribe_token(ADDRESS)
    await client.post(f"{BASE}/unsubscribe", params={"token": token})

    resp = await client.post(f"{BASE}/resubscribe", params={"token": token})

    assert resp.status_code == 200
    assert resp.json()["emails_enabled"] is True
    assert await rows(db_session, ADDRESS) == []


@pytest.mark.asyncio
async def test_turning_on_when_already_on_is_harmless(client):
    resp = await client.post(
        f"{BASE}/resubscribe", params={"token": make_unsubscribe_token(ADDRESS)}
    )

    assert resp.status_code == 200
    assert resp.json()["emails_enabled"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/unsubscribe"), ("post", "/unsubscribe"), ("post", "/resubscribe")],
)
@pytest.mark.parametrize("token", ["garbage", "a.b", "YWRh.AAAA"])
async def test_a_link_that_was_not_made_by_us_is_refused(client, db_session, method, path, token):
    resp = await getattr(client, method)(f"{BASE}{path}", params={"token": token})

    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_UNSUBSCRIBE_TOKEN"


@pytest.mark.asyncio
async def test_a_forged_link_for_someone_elses_address_changes_nothing(client, db_session):
    import base64

    _, signature = make_unsubscribe_token(ADDRESS).split(".")
    victim = base64.urlsafe_b64encode(b"victim@example.com").rstrip(b"=").decode()

    resp = await client.post(f"{BASE}/unsubscribe", params={"token": f"{victim}.{signature}"})

    assert resp.status_code == 400
    assert await rows(db_session, "victim@example.com") == []


@pytest.mark.asyncio
async def test_a_missing_token_is_a_validation_error(client):
    assert (await client.post(f"{BASE}/unsubscribe")).status_code == 422


# --- the toggle in the account --------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_account_toggle_needs_a_login(client):
    assert (await client.get(f"{BASE}/me")).status_code in (401, 403)
    assert (await client.put(f"{BASE}/me", json={"emails_enabled": False})).status_code in (
        401,
        403,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["CANDIDATE", "EMPLOYER"])
async def test_a_signed_in_user_can_turn_their_emails_off_and_on(client, db_session, role):
    token, user = await register_and_promote(client, db_session, role)
    own_address = user.email.lower()

    before = await client.get(f"{BASE}/me", headers=auth(token))
    assert before.json() == {"email": own_address, "emails_enabled": True}

    off = await client.put(f"{BASE}/me", json={"emails_enabled": False}, headers=auth(token))
    assert off.status_code == 200
    assert off.json() == {"email": own_address, "emails_enabled": False}
    [row] = await rows(db_session, own_address)
    assert row.source == "SETTINGS"
    assert (await client.get(f"{BASE}/me", headers=auth(token))).json()["emails_enabled"] is False

    on = await client.put(f"{BASE}/me", json={"emails_enabled": True}, headers=auth(token))
    assert on.json()["emails_enabled"] is True
    assert await rows(db_session, own_address) == []


@pytest.mark.asyncio
async def test_the_toggle_only_ever_changes_the_signed_in_users_own_address(client, db_session):
    token, user = await register_and_promote(client, db_session, "CANDIDATE")
    _, other = await register_and_promote(client, db_session, "CANDIDATE")

    await client.put(f"{BASE}/me", json={"emails_enabled": False}, headers=auth(token))

    assert len(await rows(db_session, user.email.lower())) == 1
    assert await rows(db_session, other.email.lower()) == []


@pytest.mark.asyncio
async def test_unsubscribing_from_an_email_shows_in_the_account_and_can_be_reversed_there(
    client, db_session
):
    token, user = await register_and_promote(client, db_session, "CANDIDATE")
    await client.post(
        f"{BASE}/unsubscribe", params={"token": make_unsubscribe_token(user.email)}
    )

    shown = await client.get(f"{BASE}/me", headers=auth(token))
    assert shown.json()["emails_enabled"] is False

    await client.put(f"{BASE}/me", json={"emails_enabled": True}, headers=auth(token))
    assert await rows(db_session, user.email.lower()) == []


@pytest.mark.asyncio
async def test_the_toggle_rejects_a_body_without_a_value(client, db_session):
    token, _ = await register_and_promote(client, db_session, "CANDIDATE")

    resp = await client.put(f"{BASE}/me", json={}, headers=auth(token))

    assert resp.status_code == 422
