"""An exhausted Anthropic balance is reported loudly, once, and changes nothing else.

When the balance runs out every call fails and each caller handles it quietly: a CV is
read as empty, a score is saved as unavailable. Nothing said why. The failure is now
recognised and reported as one grouped Sentry error; what each caller does with the
failure is unchanged."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import provider_alerts
from app.core.provider_alerts import (
    AI_CREDIT_EXHAUSTED,
    REPORT_EVERY_SECONDS,
    looks_like_credit_exhausted,
    report_if_credit_exhausted,
)
from app.modules.ai.service import AnthropicCVExtractionService

# What the API actually sends when the balance is gone (a 400, not a 402).
OUT_OF_CREDIT = Exception(
    "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API. "
    "Please go to Plans & Billing to upgrade or purchase credits.'}}"
)


@pytest.fixture(autouse=True)
def fresh_throttle(monkeypatch):
    monkeypatch.setattr(provider_alerts, "_last_reported", {})


@pytest.fixture
def reported(monkeypatch):
    calls = MagicMock()
    monkeypatch.setattr(provider_alerts, "report_quality_signal", calls)
    return calls


# --- recognising it ---------------------------------------------------------------------


def test_the_real_out_of_credit_message_is_recognised():
    assert looks_like_credit_exhausted(OUT_OF_CREDIT)


def test_a_402_is_recognised_whatever_it_says():
    error = Exception("payment required")
    error.status_code = 402
    assert looks_like_credit_exhausted(error)


@pytest.mark.parametrize(
    "message",
    [
        "Connection error.",
        "Error code: 429 - rate limit exceeded",
        "Error code: 401 - invalid x-api-key",
        "Error code: 529 - Overloaded",
        "Error code: 400 - prompt is too long",
        "",
    ],
)
def test_other_failures_are_not_mistaken_for_it(message):
    assert not looks_like_credit_exhausted(Exception(message))


# --- reporting it -----------------------------------------------------------------------


def test_it_is_reported_as_an_error_saying_where_it_happened(reported):
    assert report_if_credit_exhausted(OUT_OF_CREDIT, where="cv_extraction") is True

    reported.assert_called_once_with(
        AI_CREDIT_EXHAUSTED, level="error", provider="anthropic", where="cv_extraction"
    )


def test_another_failure_is_not_reported_and_says_so(reported):
    assert report_if_credit_exhausted(Exception("Connection error."), where="x") is False

    reported.assert_not_called()


def test_a_burst_of_failures_is_reported_once(reported):
    for _ in range(50):
        assert report_if_credit_exhausted(OUT_OF_CREDIT, where="cv_extraction") is True

    assert reported.call_count == 1


def test_it_is_reported_again_after_the_quiet_period(reported, monkeypatch):
    clock = iter([1000.0, 1000.0 + REPORT_EVERY_SECONDS + 1])
    monkeypatch.setattr(provider_alerts.time, "monotonic", lambda: next(clock))

    report_if_credit_exhausted(OUT_OF_CREDIT, where="a")
    report_if_credit_exhausted(OUT_OF_CREDIT, where="b")

    assert reported.call_count == 2


# --- the callers behave exactly as before -----------------------------------------------


def service_failing_with(error):
    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)
    service._client = SimpleNamespace(
        messages=SimpleNamespace(create=AsyncMock(side_effect=error))
    )
    return service


@pytest.mark.asyncio
async def test_a_fit_score_still_fails_the_same_way_and_the_shortfall_is_reported(reported):
    service = service_failing_with(OUT_OF_CREDIT)

    result = await service.generate_fit_reasoning("candidate", "job")

    assert result.failed is True
    reported.assert_called_once()
    assert reported.call_args.kwargs["where"] == "fit_scoring"


@pytest.mark.asyncio
async def test_an_interview_score_still_fails_the_same_way_and_is_reported(reported):
    service = service_failing_with(OUT_OF_CREDIT)

    result = await service.score_interview_transcript("transcript", "brief")

    assert result.failed is True
    assert reported.call_args.kwargs["where"] == "interview_scoring"


@pytest.mark.asyncio
async def test_job_description_writing_still_raises_and_is_reported(reported):
    service = service_failing_with(OUT_OF_CREDIT)
    job_context = SimpleNamespace(
        title="Sales Manager", seniority="Senior", industry="FMCG", company_name="Acme",
        skills=["Negotiation"],
    )

    with pytest.raises(Exception, match="credit balance is too low"):
        await service.generate_job_description_text(
            "GENERATE", "about_the_role", None, job_context
        )

    assert reported.call_args.kwargs["where"] == "job_description"


@pytest.mark.asyncio
async def test_cv_extraction_still_returns_empty_and_is_reported(reported, monkeypatch):
    async def out_of_credit(*args, **kwargs):
        raise OUT_OF_CREDIT

    monkeypatch.setattr("app.modules.ai.service.call_structured", out_of_credit)
    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)
    service._client = SimpleNamespace()

    result = await service.extract_cv_data({}, full_text="Some CV text")

    assert result.work_history == [] and result.skills == []
    assert reported.call_args.kwargs["where"] == "cv_extraction"
