"""Tell us loudly when the AI provider has run out of credit.

When the Anthropic balance runs out every call fails, and each caller handles its own
failure quietly (a CV is read as empty, a score is saved as unavailable), so nothing says
why until someone notices the numbers. This recognises that one cause and reports it once
in a while, as an error, grouped as ONE Sentry issue that the default alert rule notices.
It never changes what the caller does with the failure.
"""

import time

from app.core.quality_signals import report_quality_signal

AI_CREDIT_EXHAUSTED = "ai_provider_credit_exhausted"

# Several calls fail at once when the balance runs out; one report per worker process is
# enough, and Sentry groups them by kind anyway.
REPORT_EVERY_SECONDS = 900

# How Anthropic words it (a 400 "invalid_request_error"): "Your credit balance is too
# low to access the Anthropic API. Please go to Plans & Billing to upgrade or purchase
# credits."
_MARKERS = ("credit balance is too low", "plans & billing", "purchase credits")

_last_reported: dict[str, float] = {}


def looks_like_credit_exhausted(error: BaseException) -> bool:
    """Whether this API error is the provider saying the account is out of credit."""
    if getattr(error, "status_code", None) == 402:
        return True
    text = str(error).lower()
    return any(marker in text for marker in _MARKERS)


def report_if_credit_exhausted(
    error: BaseException, *, where: str, provider: str = "anthropic"
) -> bool:
    """Report ``error`` if it is a credit shortfall (at most once per
    ``REPORT_EVERY_SECONDS`` per process). Returns whether it was one."""
    if not looks_like_credit_exhausted(error):
        return False
    now = time.monotonic()
    if now - _last_reported.get(provider, float("-inf")) >= REPORT_EVERY_SECONDS:
        _last_reported[provider] = now
        report_quality_signal(
            AI_CREDIT_EXHAUSTED, level="error", provider=provider, where=where
        )
    return True
