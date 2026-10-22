"""Every email Elevare sends looks the same and reads like a person wrote it.

All emails are rendered through the real sender (the Resend SDK is faked) and checked
for the shared layout (the official logo, the company footer, a named sender, a
plain-text version) and for the habits that make text read as machine-written: dashes
used as punctuation, exclamation marks, symbols and emoji, and stock marketing phrases.
A new email must be added to EVERY_EMAIL below, and a test fails if one is missing, so
none can skip these checks."""

import re
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import email as email_module
from app.core.config import settings
from app.core.email import (
    COMPANY_ADDRESS,
    COMPANY_NAME,
    EMAIL_LOGO_PATH,
    ResendEmailService,
    _html_to_text,
)

TO = "ada@example.com"
JOB = "Sales Manager"
COMPANY = "Acme Ltd"
LINK = "https://example.com/link"

# One call for every email the service can send. Sample text is plain on purpose: the
# checks are about the wording Elevare wrote, not about what a user typed.
EVERY_EMAIL = {
    "send_application_confirmation": [lambda s: s.send_application_confirmation(TO, JOB, COMPANY)],
    "send_status_update": [lambda s: s.send_status_update(TO, JOB, "SHORTLISTED")],
    "send_employer_notification": [lambda s: s.send_employer_notification(TO, JOB, "Chidi Okafor", "job-1")],
    "send_verification_email": [lambda s: s.send_verification_email(TO, "token-1")],
    "send_verification_reminder": [
        lambda s: s.send_verification_reminder(TO, "Ada", "token-1", "EMPLOYER"),
        lambda s: s.send_verification_reminder(TO, "Ada", "token-1", "CANDIDATE"),
    ],
    "send_role_switch_corrected": [
        lambda s: s.send_role_switch_corrected(TO, "Ada", "CANDIDATE"),
        lambda s: s.send_role_switch_corrected(TO, "Ada", "EMPLOYER"),
    ],
    "send_onboarding_reminder": [lambda s: s.send_onboarding_reminder(TO, "Ada")],
    "send_kyc_reminder": [lambda s: s.send_kyc_reminder(TO, "Ada", COMPANY)],
    "send_job_moderation_status": [
        lambda s: s.send_job_moderation_status(TO, {"id": "job-1", "title": JOB}, "APPROVED"),
        lambda s: s.send_job_moderation_status(
            TO, {"id": "job-1", "title": JOB}, "REJECTED", "The salary range is missing."
        ),
    ],
    "send_job_switched_off": [
        lambda s: s.send_job_switched_off(TO, {"id": "job-1", "title": JOB}, "APPLICANT_LIMIT", 3),
        lambda s: s.send_job_switched_off(TO, {"id": "job-1", "title": JOB}, "EXPIRED", 30),
        lambda s: s.send_job_switched_off(TO, {"id": "job-1", "title": JOB}, "PLAN_LAPSED"),
    ],
    "send_contact_notification": [
        lambda s: s.send_contact_notification(TO, "Visitor", "v@example.com", COMPANY, "Hello", "general")
    ],
    "send_introduction_request": [lambda s: s.send_introduction_request(TO, LINK, LINK, JOB)],
    "send_ai_interview_invite": [lambda s: s.send_ai_interview_invite(TO, LINK, JOB, COMPANY)],
    "send_interview_restart_request": [
        lambda s: s.send_interview_restart_request(TO, "Chidi Okafor", JOB, COMPANY, LINK)
    ],
    "send_introduction_accepted": [lambda s: s.send_introduction_accepted(TO, JOB, LINK)],
    "send_introduction_declined": [lambda s: s.send_introduction_declined(TO, JOB)],
    "send_introduction_request_admin": [
        lambda s: s.send_introduction_request_admin(TO, COMPANY, JOB, "Chidi Okafor")
    ],
    "send_role_notification": [lambda s: s.send_role_notification(TO, COMPANY, JOB, LINK, LINK)],
    "send_kyc_rejection": [
        lambda s: s.send_kyc_rejection(TO, COMPANY, "The registration document is unclear."),
        lambda s: s.send_kyc_rejection(TO, COMPANY, None),
    ],
    "send_kyc_approved": [lambda s: s.send_kyc_approved(TO, COMPANY)],
    "send_kyc_submission_notification": [lambda s: s.send_kyc_submission_notification(TO, COMPANY, "org-1")],
    "send_subscription_payment_failed": [
        lambda s: s.send_subscription_payment_failed(TO, COMPANY, "Professional", "1 November")
    ],
    "send_invite_email": [
        lambda s: s.send_invite_email(TO, LINK, COMPANY),
        lambda s: s.send_invite_email(TO, LINK, None),
    ],
}

# Punctuation and symbols that mark text as machine-written, and stock phrases.
FORBIDDEN_CHARACTERS = ["—", "–", "!", "✓", "✔", "✨", "→", "\U0001f680"]
FORBIDDEN_PHRASES = [
    "successfully",
    "seamless",
    "streamline",
    "leverage",
    "unlock",
    "empower",
    "delve",
    "cutting-edge",
    "game-changer",
    "we're excited",
    "we are excited",
    "rest assured",
]


@pytest.fixture
def service(monkeypatch):
    sender = ResendEmailService.__new__(ResendEmailService)
    sender._resend = SimpleNamespace(Emails=SimpleNamespace(send=MagicMock()))
    monkeypatch.setattr(email_module, "suppressed_addresses", AsyncMock(return_value=set()))
    monkeypatch.setattr(settings, "app_url", "https://elevare.example")
    monkeypatch.setattr(settings, "mail_from", "noreply@elevare.example")
    monkeypatch.setattr(settings, "api_public_url", "https://api.elevare.example")
    return sender


async def render_all(service) -> list[tuple[str, dict]]:
    """(method name, payload handed to Resend) for every email."""
    rendered = []
    for name, calls in EVERY_EMAIL.items():
        for call in calls:
            service._resend.Emails.send.reset_mock()
            await call(service)
            [payload] = [c.args[0] for c in service._resend.Emails.send.call_args_list]
            rendered.append((name, payload))
    return rendered


def visible_text(payload: dict) -> str:
    """What a reader (or an inbox preview) sees: the subject, the preview line and the
    body, without markup or styles."""
    html = re.sub(r"<style.*?</style>", "", payload["html"], flags=re.S)
    return payload["subject"] + "\n" + re.sub(r"<[^>]+>", " ", html)


def test_every_email_the_service_can_send_is_covered_here():
    sendable = {
        name
        for name in dir(ResendEmailService)
        if name.startswith("send_") and callable(getattr(ResendEmailService, name))
    }

    assert sendable == set(EVERY_EMAIL), "add the new email to EVERY_EMAIL"


@pytest.mark.asyncio
async def test_no_email_uses_dashes_exclamation_marks_symbols_or_stock_phrases(service):
    problems = []
    for name, payload in await render_all(service):
        text = visible_text(payload)
        lowered = text.lower()
        problems += [f"{name}: contains {c!r}" for c in FORBIDDEN_CHARACTERS if c in text]
        problems += [f"{name}: contains the phrase {p!r}" for p in FORBIDDEN_PHRASES if p in lowered]

    assert problems == []


@pytest.mark.asyncio
async def test_subjects_are_plain_sentences_without_title_case_or_brackets(service):
    for name, payload in await render_all(service):
        subject = payload["subject"]
        assert "—" not in subject and "!" not in subject, (name, subject)
        # No Title Case Subjects: after the first word, a lower-case word stays lower-case
        # (a name or a job title typed by a user may be capitalised, which is why only
        # the fixed words of our own wording are checked).
        for fixed in ("Application Received", "Introduction Request", "Interview Invite",
                      "Company Verified", "Verify Your", "Action Required", "New Application"):
            assert fixed not in subject, (name, subject)


@pytest.mark.asyncio
async def test_headings_are_sentence_case_not_title_case(service):
    # Names, titles and company names in the sample data may be capitalised; the words
    # Elevare wrote itself may not be.
    data_words = set(f"{COMPANY} {JOB} Chidi Okafor Ada".split())
    allowed = data_words | {"AI", "KYC", "Elevare", "I"}
    for name, payload in await render_all(service):
        for heading in re.findall(r"<h2[^>]*>(.*?)</h2>", payload["html"], flags=re.S):
            words = re.sub(r"<[^>]+>", "", heading).split()
            capitalised = [w for w in words[1:] if w[:1].isupper() and w not in allowed]
            assert capitalised == [], (name, heading)


@pytest.mark.asyncio
async def test_no_label_is_set_in_spaced_capitals(service):
    for name, payload in await render_all(service):
        assert "text-transform: uppercase" not in payload["html"], name
        assert "letter-spacing: 0.05em" not in payload["html"], name


@pytest.mark.asyncio
async def test_every_email_carries_the_official_logo_from_the_website(service):
    for name, payload in await render_all(service):
        html = payload["html"]
        assert f'src="https://elevare.example{EMAIL_LOGO_PATH}"' in html, name
        assert 'alt="Elevare Human Solutions"' in html, name
        assert 'width="150"' in html, name  # sized, so it does not jump when it loads


@pytest.mark.asyncio
async def test_every_email_ends_with_the_company_name_and_address(service):
    for name, payload in await render_all(service):
        assert COMPANY_NAME in payload["html"], name
        assert COMPANY_ADDRESS in payload["html"], name
        assert COMPANY_NAME in payload["text"], name


@pytest.mark.asyncio
async def test_every_email_is_sent_from_a_named_sender(service):
    for name, payload in await render_all(service):
        assert payload["from"] == "Elevare <noreply@elevare.example>", name


def test_a_configured_sender_that_already_has_a_name_is_left_alone(monkeypatch):
    monkeypatch.setattr(settings, "mail_from", "Elevare Careers <careers@elevare.example>")

    assert email_module._from_header() == "Elevare Careers <careers@elevare.example>"


@pytest.mark.asyncio
async def test_every_email_has_a_plain_text_version_without_markup(service):
    for name, payload in await render_all(service):
        text = payload["text"]
        assert text.strip(), name
        assert "<" not in text and ">" not in text, name
        assert "font-family" not in text and "&nbsp;" not in text and "&amp;" not in text, name


@pytest.mark.asyncio
async def test_the_text_version_keeps_the_links_and_drops_the_hidden_preview(service):
    await service.send_introduction_request(TO, "https://example.com/accept", "https://example.com/decline", JOB)
    text = service._resend.Emails.send.call_args.args[0]["text"]

    assert "https://example.com/accept" in text
    assert "https://example.com/decline" in text
    assert "Elevare Human Solutions" in text.splitlines()[0]  # the logo's alt text opens it
    # The hidden inbox-preview line is not repeated at the top of the text version.
    assert "would like to connect with you about the Sales Manager role." not in text.splitlines()[1]


def test_the_text_version_of_simple_html_reads_naturally():
    html = '<html><head><title>x</title></head><body><h2>Hello</h2><p>A <a href="https://a.example">link</a>.</p></body></html>'

    assert _html_to_text(html) == "Hello\nA link (https://a.example).\n"
