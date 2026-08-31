"""Shared month-bucketing helpers for the admin cost-trend endpoints.

Each cost table (CVParsingCost, InterviewCost, FitScoringCost) is queried
with its own GROUP BY date_trunc('month', ...), but the result needs to be
turned into a gap-free monthly series before it's useful for a chart — a
month with zero calls should show up as a zero point, not be silently
skipped and read as a break in the axis.
"""

from datetime import date


def month_key(d: date) -> str:
    """'2026-08-27' -> '2026-08'."""
    return d.strftime("%Y-%m")


def month_range(start: date, end: date) -> list[str]:
    """Inclusive list of 'YYYY-MM' strings from start's month to end's month."""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def effective_month_bounds(
    rows_months: list[str], from_date: date | None, to_date: date | None
) -> tuple[str, str] | None:
    """Work out the [start_month, end_month] to fill, given an optional
    explicit range and whatever months actually have data. Returns None if
    there's no data and no explicit range to anchor an empty series to."""
    end = month_key(to_date) if to_date else None
    start = month_key(from_date) if from_date else None

    if not rows_months and start is None and end is None:
        return None

    candidates_start = [m for m in [start, *rows_months] if m]
    candidates_end = [m for m in [end, *rows_months] if m]
    if not candidates_start or not candidates_end:
        return None
    return min(candidates_start), max(candidates_end)


def build_flat_series(
    rows: list, from_date: date | None, to_date: date | None
) -> list[dict]:
    """Turn a list of (month, total_cost, total_calls)-shaped rows (as
    returned by a `GROUP BY date_trunc('month', ...)` query) into a
    gap-free monthly series — a month with zero calls becomes a real 0
    point instead of a break in the axis; a month with calls but no priced
    model keeps total_cost_usd=None (unknown, not free)."""
    by_month = {row.month.strftime("%Y-%m"): row for row in rows}

    bounds = effective_month_bounds(list(by_month.keys()), from_date, to_date)
    if bounds is None:
        return []

    start_month, end_month = bounds
    months = month_range(
        date.fromisoformat(start_month + "-01"), date.fromisoformat(end_month + "-01")
    )

    series = []
    for m in months:
        row = by_month.get(m)
        if row is None:
            series.append({"month": m, "total_cost_usd": 0.0, "total_calls": 0})
        else:
            series.append(
                {
                    "month": m,
                    "total_cost_usd": float(row.total_cost)
                    if row.total_cost is not None
                    else None,
                    "total_calls": row.total_calls or 0,
                }
            )
    return series
