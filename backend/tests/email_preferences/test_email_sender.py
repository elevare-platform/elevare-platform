"""The email sender honours "emails off", and never blocks the emails a person needs.

Every email passes through ResendEmailService._send_html. The Resend SDK is faked, and
the lookup of who has turned emails off is faked, so these tests are about what the
sender does with the answer."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import settings
from app.core.email import ResendEmailService
from app.modules.email_preferences.links import UNSUBSCRIBE_SLOT
from app.modules.email_preferences.tokens import read_unsubscribe_token

TOKEN_IN_LINK = re.compile(r"unsubscribe\?token=([A-Za-z0-9_\-.]+)")


@pytest.fixture
def service():
    sender = ResendEmailService.__new__(ResendEmailService)
    sender._resend = SimpleNamespace(Emails=SimpleNamespace(send=MagicMock()))
    return sender


def sent(service) -> list[dict]:
    """The payloads handed to Resend, in order."""
    return [call.args[0] for call in service._resend.Emails.send.call_args_list]


def turned_off(monkeypatch, *addresses: str) -> AsyncMock:
    """Make these (lower-cased) addresses count as having turned emails off."""
    lookup = AsyncMock(return_value={address.lower() for address in addresses})
    monkeypatch.setattr("app.core.email.suppressed_addresses", lookup)
    return lookup


@pytest.fixture(autouse=True)
def api_url(monkeypatch):
    monkeypatch.setattr(settings, "api_public_url", "https://api.example.com")
    monkeypatch.setattr(settings, "app_url", "https://app.example.com")


# --- a non-essential email --------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_address_that_turned_emails_off_is_not_emailed(service, monkeypatch):
    lookup = turned_off(monkeypatch, "ada@example.com")

    await service.send_application_confirmation("ada@example.com", "Sales Manager", "Acme")

    assert sent(service) == []  # skipped quietly: no error, nothing sent
    lookup.assert_awaited_once_with(["ada@example.com"])


@pytest.mark.asyncio
async def test_an_address_that_did_not_is_emailed_with_its_own_unsubscribe_link(
    service, monkeypatch
):
    turned_off(monkeypatch)  # nobody

    await service.send_application_confirmation("ada@example.com", "Sales Manager", "Acme")

    [payload] = sent(service)
    assert payload["to"] == ["ada@example.com"]
    link = TOKEN_IN_LINK.search(payload["html"])
    assert link, "the footer carries an Unsubscribe link"
    assert read_unsubscribe_token(link.group(1)) == "ada@example.com"
    assert UNSUBSCRIBE_SLOT not in payload["html"]
    assert payload["html"].count("Unsubscribe</a>") == 1


@pytest.mark.asyncio
async def test_the_footer_link_opens_the_confirmation_page_on_the_website(
    service, monkeypatch
):
    turned_off(monkeypatch)

    await service.send_status_update("ada@example.com", "Sales Manager", "SHORTLISTED")

    html = sent(service)[0]["html"]
    assert 'href="https://app.example.com/unsubscribe?token=' in html


@pytest.mark.asyncio
async def test_the_one_click_headers_point_at_the_api_and_carry_the_same_token(
    service, monkeypatch
):
    turned_off(monkeypatch)

    await service.send_application_confirmation("ada@example.com", "Sales Manager", "Acme")

    headers = sent(service)[0]["headers"]
    assert headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    url = headers["List-Unsubscribe"]
    assert url.startswith("<https://api.example.com/api/v1/email-preferences/unsubscribe?token=")
    assert url.endswith(">")
    assert read_unsubscribe_token(TOKEN_IN_LINK.search(url).group(1)) == "ada@example.com"


@pytest.mark.asyncio
async def test_without_an_api_url_there_are_no_headers_but_the_footer_link_remains(
    service, monkeypatch
):
    monkeypatch.setattr(settings, "api_public_url", None)
    turned_off(monkeypatch)

    await service.send_application_confirmation("ada@example.com", "Sales Manager", "Acme")

    [payload] = sent(service)
    assert "headers" not in payload
    assert TOKEN_IN_LINK.search(payload["html"])


@pytest.mark.asyncio
async def test_the_match_ignores_upper_case_in_the_recipient(service, monkeypatch):
    turned_off(monkeypatch, "ada@example.com")

    await service.send_application_confirmation("Ada@Example.COM", "Sales Manager", "Acme")

    assert sent(service) == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "send",
    [
        lambda s: s.send_application_confirmation("ada@example.com", "Job", "Co"),
        lambda s: s.send_status_update("ada@example.com", "Job", "SHORTLISTED"),
        lambda s: s.send_employer_notification("ada@example.com", "Job", "Name", "id-1"),
    ],
    ids=["application_confirmation", "status_update", "employer_notification"],
)
async def test_ordinary_emails_stop_for_an_address_that_turned_emails_off(
    service, monkeypatch, send
):
    turned_off(monkeypatch, "ada@example.com")

    await send(service)

    assert sent(service) == []


@pytest.mark.asyncio
async def test_with_several_recipients_only_the_unsubscribed_one_is_skipped(
    service, monkeypatch
):
    turned_off(monkeypatch, "b@example.com")
    html = f"<html><body><p>Hello</p>{UNSUBSCRIBE_SLOT}</body></html>"

    await service._send_html("Subject", ["a@example.com", "b@example.com", "c@example.com"], html)

    payloads = sent(service)
    assert [p["to"] for p in payloads] == [["a@example.com"], ["c@example.com"]]
    # Each recipient has their OWN signed link, never someone else's.
    for payload in payloads:
        token = TOKEN_IN_LINK.search(payload["html"]).group(1)
        assert [read_unsubscribe_token(token)] == payload["to"]


# --- the footer when an email is not built on the shared layout --------------------------


@pytest.mark.asyncio
async def test_an_email_without_the_layout_slot_still_gets_a_link_before_the_body_closes(
    service, monkeypatch
):
    turned_off(monkeypatch)

    await service._send_html("Subject", ["ada@example.com"], "<html><body><p>Hi</p></body></html>")

    html = sent(service)[0]["html"]
    assert TOKEN_IN_LINK.search(html)
    assert html.index("Unsubscribe") < html.index("</body>")


@pytest.mark.asyncio
async def test_an_email_with_no_body_tag_gets_the_link_appended(service, monkeypatch):
    turned_off(monkeypatch)

    await service._send_html("Subject", ["ada@example.com"], "<p>Hi</p>")

    assert TOKEN_IN_LINK.search(sent(service)[0]["html"])


# --- essential emails: always sent, no unsubscribe offered --------------------------------


ESSENTIAL = pytest.mark.parametrize(
    "send",
    [
        lambda s: s.send_verification_email("ada@example.com", "verify-token"),
        lambda s: s.send_invite_email("ada@example.com", "https://x/invite", "Acme"),
        lambda s: s.send_subscription_payment_failed("ada@example.com", "Acme", "Professional", "1 Nov"),
        lambda s: s.send_contact_notification(
            "ada@example.com", "Visitor", "v@example.com", None, "Hello", "general"
        ),
    ],
    ids=["verification", "team_invite", "payment_failed", "contact_form"],
)


@ESSENTIAL
@pytest.mark.asyncio
async def test_essential_emails_are_sent_even_to_an_address_that_turned_emails_off(
    service, monkeypatch, send
):
    lookup = turned_off(monkeypatch, "ada@example.com")

    await send(service)

    [payload] = sent(service)
    assert payload["to"] == ["ada@example.com"]
    lookup.assert_not_awaited()  # not even consulted: they cannot depend on it


@ESSENTIAL
@pytest.mark.asyncio
async def test_essential_emails_offer_no_unsubscribe_link_or_headers(
    service, monkeypatch, send
):
    turned_off(monkeypatch)

    await send(service)

    [payload] = sent(service)
    assert "Unsubscribe" not in payload["html"]
    assert UNSUBSCRIBE_SLOT not in payload["html"]
    assert "headers" not in payload


# --- failures --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_delivery_failure_is_still_raised(service, monkeypatch):
    turned_off(monkeypatch)
    service._resend.Emails.send.side_effect = RuntimeError("Resend down")

    with pytest.raises(RuntimeError, match="Resend down"):
        await service.send_application_confirmation("ada@example.com", "Job", "Co")


@pytest.mark.asyncio
async def test_reply_to_is_still_passed_through(service, monkeypatch):
    turned_off(monkeypatch)

    await service._send_html(
        "Subject", ["ada@example.com"], "<p>Hi</p>", reply_to="support@example.com"
    )

    assert sent(service)[0]["reply_to"] == "support@example.com"
