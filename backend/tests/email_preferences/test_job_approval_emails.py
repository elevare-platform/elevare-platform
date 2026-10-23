"""The two approval emails added for "publish as soon as it is approved".

One says the job is live. The other says it was approved but could not be published yet, shows
why, and still offers the publish link, so an approval is never left without a next step."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import email as email_module
from app.core.config import settings
from app.core.email import ResendEmailService

TO = "employer@example.com"
JOB = {"id": "job-9", "title": "Sales Executive"}
WHY = "Your plan allows one new job a month, and you have already published one this month."


@pytest.fixture
def service(monkeypatch):
    sender = ResendEmailService.__new__(ResendEmailService)
    sender._resend = SimpleNamespace(Emails=SimpleNamespace(send=MagicMock()))
    monkeypatch.setattr(email_module, "suppressed_addresses", AsyncMock(return_value=set()))
    monkeypatch.setattr(settings, "app_url", "https://elevare.example")
    monkeypatch.setattr(settings, "mail_from", "noreply@elevare.example")
    monkeypatch.setattr(settings, "api_public_url", "https://api.elevare.example")
    return sender


async def _sent(service, action, reason=None) -> dict:
    await service.send_job_moderation_status(TO, JOB, action, reason)
    [payload] = [c.args[0] for c in service._resend.Emails.send.call_args_list]
    return payload


@pytest.mark.asyncio
async def test_the_live_email_says_the_job_is_live_and_links_to_its_applicants(service):
    payload = await _sent(service, "APPROVED_AND_PUBLISHED")

    assert payload["subject"] == "Your job is live: Sales Executive"
    assert "approved <strong>Sales Executive</strong> and published it, as you asked" in payload["html"]
    assert "https://elevare.example/employer/jobs/job-9/applicants" in payload["html"]
    assert "Publish job" not in payload["html"]  # it is already published


@pytest.mark.asyncio
async def test_the_not_published_email_shows_why_and_offers_the_publish_link(service):
    payload = await _sent(service, "APPROVED_NOT_PUBLISHED", WHY)

    assert payload["subject"] == "Your job listing was approved: Sales Executive"
    assert "You asked us to publish it as soon as it was approved, but we couldn't do that yet" in payload["html"]
    assert WHY in payload["html"]
    assert "https://elevare.example/employer/jobs/job-9/publish" in payload["html"]


@pytest.mark.asyncio
async def test_the_plain_approval_email_is_unchanged(service):
    payload = await _sent(service, "APPROVED")

    assert payload["subject"] == "Your job listing was approved: Sales Executive"
    assert "You can publish it now" in payload["html"]


@pytest.mark.asyncio
async def test_they_are_written_the_way_the_rest_of_the_product_is(service):
    for action, reason in [("APPROVED_AND_PUBLISHED", None), ("APPROVED_NOT_PUBLISHED", WHY)]:
        service._resend.Emails.send.reset_mock()
        payload = await _sent(service, action, reason)
        for part in ("subject", "text"):
            assert "!" not in payload[part]
            assert "—" not in payload[part] and "–" not in payload[part]
