"""Cost calculators for external LLM/audio API calls.

Every rate constant below is a PLACEHOLDER that must be checked against the
provider's live pricing page before being trusted for real budgeting —
prices drift, and a stale constant produces a wrong-but-plausible-looking
number that's worse than no number at all. Each constant carries the page
it was last checked against and the date. Re-verify before relying on this
for a real cost report.

All three ``compute_*`` functions return ``None`` (never ``0``) when a
model isn't in the pricing table, so a missing price never gets silently
reported as free — callers should persist the raw usage with a NULL
``cost_usd`` rather than drop the row or guess.
"""

from decimal import Decimal

# ---------------------------------------------------------------------------
# Anthropic Claude — per-token pricing, $ per 1,000,000 tokens.
#
# Rates are per-model dicts so prompt-cache writes/hits can be priced
# separately from base input/output — Anthropic bills those at different
# rates. None of the Claude calls in this codebase currently enable prompt
# caching (no `cache_control` blocks), so cache token counts are always 0
# today, but the table carries real cache rates where known rather than
# guessing them, so a cache_*_per_mtok of None here means "unknown," not
# "free" — see compute_anthropic_cost_usd's handling of that.
# ---------------------------------------------------------------------------
ANTHROPIC_TOKEN_PRICES: dict[str, dict[str, Decimal | None]] = {
    # claude-sonnet-4-6 — settings.anthropic_model's actual configured value.
    # Rates as given directly by the user, 2026-08-25 (not independently
    # verified against Anthropic's pricing page — re-check if in doubt).
    "claude-sonnet-4-6": {
        "input_per_mtok": Decimal("3.00"),
        "output_per_mtok": Decimal("15.00"),
        "cache_write_5m_per_mtok": Decimal("3.75"),
        "cache_write_1h_per_mtok": Decimal("6.00"),
        "cache_hit_per_mtok": Decimal("0.30"),
    },
    # Older snapshot model, kept as a placeholder in case anything still
    # references it — base input/output only, cache rates unconfirmed.
    # Source: https://www.anthropic.com/pricing — PLACEHOLDER, verify before use.
    "claude-3-5-sonnet-20241022": {
        "input_per_mtok": Decimal("3.00"),
        "output_per_mtok": Decimal("15.00"),
        "cache_write_5m_per_mtok": None,
        "cache_write_1h_per_mtok": None,
        "cache_hit_per_mtok": None,
    },
    # settings.anthropic_model_fast's configured value — the tiering
    # "fast pass" model for CV extraction and fit reasoning.
    # PLACEHOLDER — not independently verified against Anthropic's pricing
    # page, re-check before trusting for real budgeting.
    "claude-haiku-4-5": {
        "input_per_mtok": Decimal("1.00"),
        "output_per_mtok": Decimal("5.00"),
        "cache_write_5m_per_mtok": Decimal("1.25"),
        "cache_write_1h_per_mtok": Decimal("2.00"),
        "cache_hit_per_mtok": Decimal("0.10"),
    },
}

# ---------------------------------------------------------------------------
# OpenAI Realtime API — per-token pricing, $ per 1,000,000 tokens, split by
# modality (audio tokens are priced very differently from text tokens) and
# by cache status for input.
# Source: https://openai.com/api/pricing/ — PLACEHOLDER, verify before use.
# ---------------------------------------------------------------------------
OPENAI_REALTIME_PRICES: dict[str, dict[str, Decimal]] = {
    "gpt-realtime": {
        "text_input_per_mtok": Decimal("5.00"),
        "text_output_per_mtok": Decimal("20.00"),
        "audio_input_per_mtok": Decimal("40.00"),
        "audio_output_per_mtok": Decimal("80.00"),
        "cached_text_input_per_mtok": Decimal("2.50"),
        "cached_audio_input_per_mtok": Decimal("2.50"),
    },
}

# ---------------------------------------------------------------------------
# OpenAI Whisper transcription — $ per minute of audio.
# Source: https://openai.com/api/pricing/ — PLACEHOLDER, verify before use.
# ---------------------------------------------------------------------------
OPENAI_TRANSCRIPTION_PRICES: dict[str, Decimal] = {
    "whisper-1": Decimal("0.006"),
}

_MTOK = Decimal(1_000_000)


def compute_anthropic_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_5m_tokens: int = 0,
    cache_write_1h_tokens: int = 0,
    cache_hit_tokens: int = 0,
) -> Decimal | None:
    """Cost of one Anthropic Messages API call, or None if the model isn't priced.

    Cache token counts default to 0 — none of the current call sites
    enable prompt caching, so `response.usage.cache_creation_input_tokens`/
    `cache_read_input_tokens` are never populated yet. If a nonzero cache
    count is ever passed for a model whose cache rate isn't known (None in
    ANTHROPIC_TOKEN_PRICES), this returns None rather than silently
    pricing that portion as free.
    """
    rates = ANTHROPIC_TOKEN_PRICES.get(model)
    if rates is None:
        return None

    def _priced(tokens: int, rate: Decimal | None) -> Decimal | None:
        if tokens <= 0:
            return Decimal(0)
        if rate is None:
            return None
        return Decimal(tokens) / _MTOK * rate

    parts = [
        _priced(input_tokens, rates["input_per_mtok"]),
        _priced(output_tokens, rates["output_per_mtok"]),
        _priced(cache_write_5m_tokens, rates["cache_write_5m_per_mtok"]),
        _priced(cache_write_1h_tokens, rates["cache_write_1h_per_mtok"]),
        _priced(cache_hit_tokens, rates["cache_hit_per_mtok"]),
    ]
    if any(p is None for p in parts):
        return None
    return sum(parts, Decimal(0))


def compute_realtime_cost_usd(model: str, usage: dict) -> Decimal | None:
    """Cost of one Realtime session's accumulated usage, or None if the model isn't priced.

    ``usage`` is the raw ``response.usage``-shaped dict (or the
    frontend-forwarded equivalent): top-level ``input_tokens``/
    ``output_tokens`` plus ``input_token_details``/``output_token_details``
    breaking each down into ``text_tokens``/``audio_tokens``/
    ``cached_tokens``. Each bucket is priced at its own rate — audio and
    text tokens are not interchangeable for billing purposes.
    """
    rates = OPENAI_REALTIME_PRICES.get(model)
    if rates is None:
        return None

    input_details = usage.get("input_token_details") or {}
    output_details = usage.get("output_token_details") or {}

    cached_text = Decimal(input_details.get("cached_text_tokens", 0) or 0)
    cached_audio = Decimal(input_details.get("cached_audio_tokens", 0) or 0)
    text_input = Decimal(input_details.get("text_tokens", 0) or 0) - cached_text
    audio_input = Decimal(input_details.get("audio_tokens", 0) or 0) - cached_audio
    text_output = Decimal(output_details.get("text_tokens", 0) or 0)
    audio_output = Decimal(output_details.get("audio_tokens", 0) or 0)

    # If the API didn't break usage down into text/audio sub-buckets, fall
    # back to treating the whole total as audio — the dominant, more
    # expensive component for a voice interview — rather than silently
    # under-billing it as text.
    if not input_details and not output_details:
        audio_input = Decimal(usage.get("input_tokens", 0) or 0)
        audio_output = Decimal(usage.get("output_tokens", 0) or 0)

    return (
        max(text_input, 0) / _MTOK * rates["text_input_per_mtok"]
        + max(audio_input, 0) / _MTOK * rates["audio_input_per_mtok"]
        + text_output / _MTOK * rates["text_output_per_mtok"]
        + audio_output / _MTOK * rates["audio_output_per_mtok"]
        + cached_text / _MTOK * rates["cached_text_input_per_mtok"]
        + cached_audio / _MTOK * rates["cached_audio_input_per_mtok"]
    )


def compute_transcription_cost_usd(
    model: str, duration_seconds: float
) -> Decimal | None:
    """Cost of one Whisper transcription call, or None if the model isn't priced.

    Billed per minute, rounded up to the next full minute — confirm this
    rounding rule against OpenAI's current pricing page; if they bill by
    the second instead, drop the ceiling and price the exact duration.
    """
    rate = OPENAI_TRANSCRIPTION_PRICES.get(model)
    if rate is None:
        return None
    minutes = Decimal(duration_seconds) / Decimal(60)
    billed_minutes = minutes.to_integral_value(rounding="ROUND_CEILING")
    if billed_minutes < 1:
        billed_minutes = Decimal(1)
    return billed_minutes * rate
