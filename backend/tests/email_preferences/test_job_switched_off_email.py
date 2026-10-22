"""The email an employer gets when the platform switches one of their jobs off.

It says which job, why, that the applicants are kept, and where to go: the applicants page and
the plans. Each reason reads in plain words, and the number the reason quotes is shown."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import email as email_module
from app.core.config import settings
from app.core.email import ResendEmailService

TO = "employer@example.com"
JOB = {"id": "job-9", "title": "Sales Executive"}


@pytest.fixture
def service(monkeypatch):
    sender = ResendEmailService.__new__(ResendEmailService)
    sender._resend = SimpleNamespace(Emails=SimpleNamespace(send=MagicMock()))
    monkeypatch.setattr(email_module, "suppressed_addresses", AsyncMock(return_value=set()))
    monkeypatch.setattr(settings, "app_url", "https://elevare.example")
    monkeypatch.setattr(settings, "mail_from", "noreply@elevare.example")
    monkeypatch.setattr(settings, "api_public_url", "https://api.elevare.example")
    return sender


async def _sent(service, reason, detail=None) -> dict:
    await service.send_job_switched_off(TO, JOB, reason, detail)
    [payload] = [c.args[0] for c in service._resend.Emails.send.call_args_list]
    return payload


@pytest.mark.asyncio
async def test_it_goes_to_the_employer_with_the_job_in_the_subject(service):
    payload = await _sent(service, "APPLICANT_LIMIT", 3)

    assert payload["to"] == [TO]
    assert payload["subject"] == "Your job has been switched off: Sales Executive"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "detail", "phrase"),
    [
        ("APPLICANT_LIMIT", 10, "it reached 10 applicants, the most your plan allows for one job"),
        ("APPLICANT_LIMIT", 3, "it reached 3 applicants, the most your plan allows for one job"),
        ("EXPIRED", 30, "it ran for 30 days, the longest your plan allows"),
        ("PLAN_LAPSED", None, "your plan has ended"),
    ],
)
async def test_it_says_why_in_plain_words(service, reason, detail, phrase):
    payload = await _sent(service, reason, detail)

    assert phrase in payload["html"]
    assert phrase in payload["text"]


@pytest.mark.asyncio
async def test_it_says_the_applicants_are_kept_and_what_to_do(service):
    payload = await _sent(service, "EXPIRED", 30)

    assert "Every applicant is kept" in payload["html"]
    assert "upgrade your plan" in payload["html"]


@pytest.mark.asyncio
async def test_it_links_to_the_applicants_and_to_the_plans(service):
    payload = await _sent(service, "EXPIRED", 30)

    assert "https://elevare.example/employer/jobs/job-9/applicants" in payload["html"]
    assert "https://elevare.example/pricing" in payload["html"]


@pytest.mark.asyncio
async def test_it_is_written_the_way_the_rest_of_the_product_is(service):
    """No dashes and no exclamation marks in what Elevare wrote."""
    for reason, detail in [("APPLICANT_LIMIT", 3), ("EXPIRED", 30), ("PLAN_LAPSED", None)]:
        service._resend.Emails.send.reset_mock()
        payload = await _sent(service, reason, detail)
        for part in ("subject", "text"):
            assert "!" not in payload[part], f"{reason}: exclamation mark in {part}"
            assert "—" not in payload[part] and "–" not in payload[part]
