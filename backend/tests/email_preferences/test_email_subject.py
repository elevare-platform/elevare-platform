"""An email subject is always one clean line.

Subjects include things people typed (a job title, a name, a company). A line break in
one was refused by the mail provider (a Sentry error on the introduction email) and is how
email header injection works. The cleaning is done once, where every email is sent."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.email import MAX_SUBJECT_LENGTH, ResendEmailService, _clean_subject


@pytest.fixture
def service(monkeypatch):
    sender = ResendEmailService.__new__(ResendEmailService)
    sender._resend = SimpleNamespace(Emails=SimpleNamespace(send=MagicMock()))
    # Nobody has turned emails off.
    monkeypatch.setattr("app.core.email.suppressed_addresses", AsyncMock(return_value=set()))
    return sender


def subject_sent(service) -> str:
    [call] = service._resend.Emails.send.call_args_list
    return call.args[0]["subject"]


# --- the cleaning -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "dirty,clean",
    [
        ("Introduction request: Sales Manager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales\nManager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales\r\nManager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales\rManager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales\tManager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales Manager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales Manager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales\x85Manager", "Introduction request: Sales Manager"),
        ("Introduction request: Sales\x00Manager\x1b", "Introduction request: Sales Manager"),
        ("  Introduction request:   Sales   Manager  ", "Introduction request: Sales Manager"),
        ("Introduction request: \nSales Manager\n", "Introduction request: Sales Manager"),
    ],
)
def test_line_breaks_and_control_characters_become_one_space(dirty, clean):
    assert _clean_subject(dirty) == clean


def test_a_header_injection_attempt_stays_on_one_line():
    attack = "Introduction request: Sales\r\nBcc: attacker@example.com\r\n\r\nSend me everything"

    cleaned = _clean_subject(attack)

    assert "\r" not in cleaned and "\n" not in cleaned
    assert cleaned == "Introduction request: Sales Bcc: attacker@example.com Send me everything"


def test_ordinary_punctuation_and_accents_are_left_alone():
    subject = "Application update: Chargé d’affaires, Lagos (2nd round) / Ìbàdàn & Abuja"

    assert _clean_subject(subject) == subject


def test_a_very_long_subject_is_cut_without_leaving_a_trailing_space():
    cleaned = _clean_subject("Introduction request: " + "word " * 100)

    assert len(cleaned) <= MAX_SUBJECT_LENGTH
    assert cleaned == cleaned.rstrip()


def test_an_empty_or_blank_subject_stays_empty_rather_than_failing():
    assert _clean_subject("") == ""
    assert _clean_subject(" \n\t ") == ""


# --- where it is applied ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_introduction_email_is_sent_with_a_one_line_subject(service):
    """The email from the Sentry report: a job title with a line break in it."""
    await service.send_introduction_request(
        "ada@example.com",
        "https://app.example.com/accept",
        "https://app.example.com/decline",
        "Sales\nManager",
    )

    assert subject_sent(service) == "Introduction request: Sales Manager"


@pytest.mark.asyncio
async def test_another_email_with_a_typed_value_in_its_subject_is_cleaned_too(service):
    """The cleaning is at the one place every email is sent, not in each email."""
    await service.send_application_confirmation("ada@example.com", "Sales\r\nManager", "Acme")

    assert subject_sent(service) == "Application received: Sales Manager"


@pytest.mark.asyncio
async def test_essential_emails_are_cleaned_too(service):
    await service._send_html(
        "Verify\nyour email", ["ada@example.com"], "<p>Hello</p>", essential=True
    )

    assert subject_sent(service) == "Verify your email"
