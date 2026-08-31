"""Tests for the month-bucketing helpers behind the admin cost-trend endpoints."""

from datetime import date
from types import SimpleNamespace

from app.core.cost_trend import build_flat_series, effective_month_bounds, month_range


def test_month_range_is_inclusive_of_both_ends():
    assert month_range(date(2026, 6, 15), date(2026, 8, 1)) == [
        "2026-06",
        "2026-07",
        "2026-08",
    ]


def test_month_range_handles_year_rollover():
    assert month_range(date(2025, 11, 1), date(2026, 2, 1)) == [
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]


def test_effective_month_bounds_no_data_no_range_returns_none():
    assert effective_month_bounds([], None, None) is None


def test_effective_month_bounds_prefers_explicit_range_over_data():
    bounds = effective_month_bounds(
        ["2026-07"], date(2026, 1, 1), date(2026, 3, 1)
    )
    # Explicit range must win even though it doesn't cover where the data is —
    # the caller asked for Jan-Mar, that's what should be filled.
    assert bounds == ("2026-01", "2026-07")


def test_effective_month_bounds_falls_back_to_data_when_no_range_given():
    assert effective_month_bounds(["2026-05", "2026-07"], None, None) == (
        "2026-05",
        "2026-07",
    )


def _row(month_str, total_cost, total_calls):
    return SimpleNamespace(
        month=date.fromisoformat(month_str + "-01"),
        total_cost=total_cost,
        total_calls=total_calls,
    )


def test_build_flat_series_fills_gap_months_with_real_zero():
    rows = [_row("2026-06", None, 0)]
    series = build_flat_series(rows, date(2026, 6, 1), date(2026, 8, 1))
    assert series == [
        {"month": "2026-06", "total_cost_usd": None, "total_calls": 0},
        {"month": "2026-07", "total_cost_usd": 0.0, "total_calls": 0},
        {"month": "2026-08", "total_cost_usd": 0.0, "total_calls": 0},
    ]


def test_build_flat_series_preserves_unpriced_none_distinct_from_zero_calls():
    """A month with real calls but no priced model must stay None, not
    collapse into the same 0.0 a genuinely quiet month gets."""
    rows = [_row("2026-06", None, 3)]
    series = build_flat_series(rows, date(2026, 6, 1), date(2026, 6, 1))
    assert series == [{"month": "2026-06", "total_cost_usd": None, "total_calls": 3}]


def test_build_flat_series_empty_with_no_range_returns_empty():
    assert build_flat_series([], None, None) == []
