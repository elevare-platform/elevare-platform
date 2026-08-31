"""Tests for the LLM/audio cost calculators in app/core/ai_pricing.py.

These assert arithmetic against the module's own rate constants (not
hand-typed dollar amounts) so the tests stay correct if the placeholder
rates get updated to real, verified provider prices — what matters here is
that the formulas are right, not that any specific number is memorized.
"""

from decimal import Decimal

from app.core.ai_pricing import (
    ANTHROPIC_TOKEN_PRICES,
    OPENAI_REALTIME_PRICES,
    OPENAI_TRANSCRIPTION_PRICES,
    compute_anthropic_cost_usd,
    compute_realtime_cost_usd,
    compute_transcription_cost_usd,
)

_ANTHROPIC_MODEL = next(iter(ANTHROPIC_TOKEN_PRICES))
_REALTIME_MODEL = next(iter(OPENAI_REALTIME_PRICES))
_TRANSCRIPTION_MODEL = next(iter(OPENAI_TRANSCRIPTION_PRICES))


def test_anthropic_cost_matches_hand_computed_value():
    rates = ANTHROPIC_TOKEN_PRICES[_ANTHROPIC_MODEL]
    cost = compute_anthropic_cost_usd(_ANTHROPIC_MODEL, 1_000_000, 1_000_000)
    assert cost == rates["input_per_mtok"] + rates["output_per_mtok"]


def test_anthropic_cost_prices_cache_tokens_at_their_own_rate():
    rates = ANTHROPIC_TOKEN_PRICES[_ANTHROPIC_MODEL]
    cost = compute_anthropic_cost_usd(
        _ANTHROPIC_MODEL,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_write_5m_tokens=1_000_000,
        cache_write_1h_tokens=1_000_000,
        cache_hit_tokens=1_000_000,
    )
    expected = (
        rates["input_per_mtok"]
        + rates["output_per_mtok"]
        + rates["cache_write_5m_per_mtok"]
        + rates["cache_write_1h_per_mtok"]
        + rates["cache_hit_per_mtok"]
    )
    assert cost == expected


def test_anthropic_cost_unpriced_cache_tier_returns_none_not_free():
    """claude-3-5-sonnet-20241022's cache rates are unconfirmed (None) — a
    nonzero cache count for it must not be silently priced as free."""
    model = "claude-3-5-sonnet-20241022"
    assert ANTHROPIC_TOKEN_PRICES[model]["cache_hit_per_mtok"] is None

    priced_without_cache = compute_anthropic_cost_usd(model, 1000, 1000)
    assert priced_without_cache is not None

    priced_with_unknown_cache = compute_anthropic_cost_usd(
        model, 1000, 1000, cache_hit_tokens=500
    )
    assert priced_with_unknown_cache is None


def test_anthropic_cost_unknown_model_returns_none_not_zero():
    assert compute_anthropic_cost_usd("not-a-real-model", 1000, 1000) is None


def test_anthropic_cost_zero_tokens_is_zero():
    assert compute_anthropic_cost_usd(_ANTHROPIC_MODEL, 0, 0) == Decimal(0)


def test_realtime_cost_prices_each_bucket_at_its_own_rate():
    """The case most likely to be implemented wrong — audio tokens must
    not be priced at the (much cheaper) text rate."""
    rates = OPENAI_REALTIME_PRICES[_REALTIME_MODEL]
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 1_000_000,
        "input_token_details": {
            "text_tokens": 500_000,
            "audio_tokens": 300_000,
            "cached_text_tokens": 100_000,
            "cached_audio_tokens": 100_000,
        },
        "output_token_details": {
            "text_tokens": 400_000,
            "audio_tokens": 600_000,
        },
    }
    cost = compute_realtime_cost_usd(_REALTIME_MODEL, usage)

    mtok = Decimal(1_000_000)
    expected = (
        Decimal(400_000) / mtok * rates["text_input_per_mtok"]  # 500k text - 100k cached
        + Decimal(200_000) / mtok * rates["audio_input_per_mtok"]  # 300k audio - 100k cached
        + Decimal(400_000) / mtok * rates["text_output_per_mtok"]
        + Decimal(600_000) / mtok * rates["audio_output_per_mtok"]
        + Decimal(100_000) / mtok * rates["cached_text_input_per_mtok"]
        + Decimal(100_000) / mtok * rates["cached_audio_input_per_mtok"]
    )
    assert cost == expected


def test_realtime_cost_without_breakdown_treats_total_as_audio():
    """No input_token_details/output_token_details at all (older event
    shape, or a frontend-side accumulation bug) must not silently price
    everything at the cheaper text rate — audio is the dominant, more
    expensive component for a voice interview, so that's the safe default."""
    rates = OPENAI_REALTIME_PRICES[_REALTIME_MODEL]
    usage = {"input_tokens": 1_000_000, "output_tokens": 500_000}
    cost = compute_realtime_cost_usd(_REALTIME_MODEL, usage)

    mtok = Decimal(1_000_000)
    expected = (
        Decimal(1_000_000) / mtok * rates["audio_input_per_mtok"]
        + Decimal(500_000) / mtok * rates["audio_output_per_mtok"]
    )
    assert cost == expected


def test_realtime_cost_unknown_model_returns_none():
    assert compute_realtime_cost_usd("not-a-real-model", {"input_tokens": 1}) is None


def test_transcription_cost_rounds_up_to_next_minute():
    rate = OPENAI_TRANSCRIPTION_PRICES[_TRANSCRIPTION_MODEL]
    # 61 seconds must bill as 2 minutes, not 1.0167.
    cost = compute_transcription_cost_usd(_TRANSCRIPTION_MODEL, 61)
    assert cost == rate * 2


def test_transcription_cost_exact_minute_bills_that_minute():
    rate = OPENAI_TRANSCRIPTION_PRICES[_TRANSCRIPTION_MODEL]
    cost = compute_transcription_cost_usd(_TRANSCRIPTION_MODEL, 120)
    assert cost == rate * 2


def test_transcription_cost_short_clip_bills_minimum_one_minute():
    rate = OPENAI_TRANSCRIPTION_PRICES[_TRANSCRIPTION_MODEL]
    cost = compute_transcription_cost_usd(_TRANSCRIPTION_MODEL, 5)
    assert cost == rate


def test_transcription_cost_unknown_model_returns_none():
    assert compute_transcription_cost_usd("not-a-real-model", 60) is None
