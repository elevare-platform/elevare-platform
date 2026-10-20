"""Text a user typed is shown as text in every email, never run as markup.

A job title, a name or a company is typed by one person and shown in an email to
another. Put into the HTML unescaped, a title such as `<a href="https://evil.example">
Confirm your account</a>` becomes a real link inside a genuine Elevare email. Every email
is rendered through the real sender with a hostile value in each free-text field and the
HTML is checked. The subject is plain text, so it must show the value as typed, not as
`&lt;` and `&amp;`."""

import html as html_lib
import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import email as email_module
from app.core.config import settings
from app.core.email import ResendEmailService

TO = "ada@example.com"
LINK = "https://example.com/link"

# Markup, a script, and both kinds of quote (for a value that lands inside an attribute).
HOSTILE = '<b>x</b> <script>alert(1)</script> "q" \'s\' Q&A'
ESCAPED = html_lib.escape(HOSTILE, quote=True)

# One call per email that shows typed text, with the hostile value in EVERY free-text
# field. Links, tokens and recipient addresses are built by Elevare, not typed, and stay plain.
HOSTILE_EMAILS = {
    "send_application_confirmation": lambda s: s.send_application_confirmation(TO, HOSTILE, HOSTILE),
    "send_status_update": lambda s: s.send_status_update(TO, HOSTILE, "SHORTLISTED"),
    "send_employer_notification": lambda s: s.send_employer_notification(TO, HOSTILE, HOSTILE, "job-1"),
    "send_verification_reminder": lambda s: s.send_verification_reminder(TO, HOSTILE, "token-1", "EMPLOYER"),
    "send_verification_reminder (candidate)": lambda s: s.send_verification_reminder(TO, HOSTILE, "token-1", "CANDIDATE"),
    "send_role_switch_corrected": lambda s: s.send_role_switch_corrected(TO, HOSTILE, "CANDIDATE"),
    "send_role_switch_corrected (employer)": lambda s: s.send_role_switch_corrected(TO, HOSTILE, "EMPLOYER"),
    "send_onboarding_reminder": lambda s: s.send_onboarding_reminder(TO, HOSTILE),
    "send_kyc_reminder": lambda s: s.send_kyc_reminder(TO, HOSTILE, HOSTILE),
    "send_job_moderation_status (approved)": lambda s: s.send_job_moderation_status(
        TO, {"id": "job-1", "title": HOSTILE}, "APPROVED"
    ),
    "send_job_moderation_status (rejected)": lambda s: s.send_job_moderation_status(
        TO, {"id": "job-1", "title": HOSTILE}, "REJECTED", HOSTILE
    ),
    "send_contact_notification": lambda s: s.send_contact_notification(
        TO, HOSTILE, "v@example.com", HOSTILE, HOSTILE, "general"
    ),
    "send_introduction_request": lambda s: s.send_introduction_request(TO, LINK, LINK, HOSTILE),
    "send_ai_interview_invite": lambda s: s.send_ai_interview_invite(TO, LINK, HOSTILE, HOSTILE),
    "send_interview_restart_request": lambda s: s.send_interview_restart_request(
        TO, HOSTILE, HOSTILE, HOSTILE, LINK
    ),
    "send_introduction_accepted": lambda s: s.send_introduction_accepted(TO, HOSTILE, LINK),
    "send_introduction_declined": lambda s: s.send_introduction_declined(TO, HOSTILE),
    "send_introduction_request_admin": lambda s: s.send_introduction_request_admin(
        TO, HOSTILE, HOSTILE, HOSTILE
    ),
    "send_role_notification": lambda s: s.send_role_notification(TO, HOSTILE, HOSTILE, LINK, LINK),
    "send_kyc_rejection": lambda s: s.send_kyc_rejection(TO, HOSTILE, HOSTILE),
    "send_kyc_approved": lambda s: s.send_kyc_approved(TO, HOSTILE),
    "send_kyc_submission_notification": lambda s: s.send_kyc_submission_notification(TO, HOSTILE, "org-1"),
    "send_subscription_payment_failed": lambda s: s.send_subscription_payment_failed(
        TO, HOSTILE, HOSTILE, HOSTILE
    ),
    "send_invite_email": lambda s: s.send_invite_email(TO, LINK, HOSTILE),
}

# Emails that show nothing a person typed (a link and a token only).
SHOWS_NO_TYPED_TEXT = {"send_verification_email"}


def test_every_email_the_service_can_send_is_checked_here():
    """A new email must be added to HOSTILE_EMAILS (with a hostile value in each field a
    person types), or listed above as showing no typed text. Otherwise it could put a
    stranger's markup into an email unnoticed."""
    sendable = {
        name
        for name in dir(ResendEmailService)
        if name.startswith("send_") and callable(getattr(ResendEmailService, name))
    }
    checked = {name.split(" (")[0] for name in HOSTILE_EMAILS} | SHOWS_NO_TYPED_TEXT

    assert sendable == checked, "add the new email to HOSTILE_EMAILS"


# What must never appear raw in the HTML of any email.
RAW_FRAGMENTS = ["<b>x</b>", "<script>", "</script>", '"q"', "'s'"]


@pytest.fixture
def service(monkeypatch):
    sender = ResendEmailService.__new__(ResendEmailService)
    sender._resend = SimpleNamespace(Emails=SimpleNamespace(send=MagicMock()))
    monkeypatch.setattr(email_module, "suppressed_addresses", AsyncMock(return_value=set()))
    monkeypatch.setattr(settings, "app_url", "https://elevare.example")
    monkeypatch.setattr(settings, "mail_from", "noreply@elevare.example")
    monkeypatch.setattr(settings, "api_public_url", "https://api.elevare.example")
    return sender


async def payload_of(service, call) -> dict:
    service._resend.Emails.send.reset_mock()
    await call(service)
    [sent] = [c.args[0] for c in service._resend.Emails.send.call_args_list]
    return sent


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(HOSTILE_EMAILS))
async def test_typed_text_is_never_run_as_markup(service, name):
    payload = await payload_of(service, HOSTILE_EMAILS[name])

    for fragment in RAW_FRAGMENTS:
        assert fragment not in payload["html"], f"{name}: {fragment!r} reached the HTML unescaped"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(HOSTILE_EMAILS))
async def test_typed_text_is_still_shown_as_text(service, name):
    """Escaping must not drop the value: the reader still sees what was typed."""
    payload = await payload_of(service, HOSTILE_EMAILS[name])

    assert ESCAPED in payload["html"], f"{name}: the typed value is not shown"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(HOSTILE_EMAILS))
async def test_the_plain_text_version_reads_as_typed(service, name):
    """The text part is made from the HTML, so it must read `Q&A`, not `Q&amp;A`."""
    payload = await payload_of(service, HOSTILE_EMAILS[name])

    assert "&amp;" not in payload["text"] and "&lt;" not in payload["text"]
    assert "Q&A" in payload["text"]


@pytest.mark.asyncio
@pytest.mark.parametrize("name", list(HOSTILE_EMAILS))
async def test_the_subject_is_plain_text_not_html(service, name):
    payload = await payload_of(service, HOSTILE_EMAILS[name])

    assert not re.search(r"&(amp|lt|gt|quot|#x27);", payload["subject"]), payload["subject"]


@pytest.mark.asyncio
async def test_a_title_with_an_ampersand_reads_normally_in_the_subject(service):
    payload = await payload_of(
        service, lambda s: s.send_application_confirmation(TO, "Sales & Marketing Manager", "Acme & Sons")
    )

    assert payload["subject"] == "Application received: Sales & Marketing Manager"
    assert "Sales &amp; Marketing Manager" in payload["html"]


@pytest.mark.asyncio
async def test_a_visitors_address_with_an_apostrophe_is_shown_as_typed(service):
    payload = await payload_of(
        service,
        lambda s: s.send_contact_notification(TO, "Visitor", "o'brien@example.com", None, "Hello", "general"),
    )

    # Escaped in the HTML (an apostrophe could close an attribute), and read back as typed.
    assert "o&#x27;brien@example.com" in payload["html"]
    assert "o'brien@example.com" in payload["text"]
    assert payload["to"] == [TO]


@pytest.mark.asyncio
async def test_a_value_with_nothing_special_in_it_is_unchanged(service):
    payload = await payload_of(service, lambda s: s.send_introduction_request(TO, LINK, LINK, "Sales Manager"))

    assert "Sales Manager" in payload["html"]
    assert payload["subject"] == "Introduction request: Sales Manager"
