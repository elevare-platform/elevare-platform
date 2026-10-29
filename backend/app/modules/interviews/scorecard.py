"""The interview scorecard, laid out as Elevare's printed scorecard (docs/08_DECISIONS.md, item 56).

A table of Competency, Weight, Rating /5, Weighted Points and Evidence / Verification, a total as
points out of half the total weight (37.5 / 50) with the 100-point total beside it (75 / 100), then
the practical case rating, the strengths and the human decision. Built from the weighted report the
screens already show (so a reviewed rating or total is the one used) and what an Elevare admin
filled in by hand. Plain functions, no database.
"""

from __future__ import annotations

# A competency's points are its rating times its weight over ten, so a full set of 5s earns half
# the total weight (50 for a total weight of 100), as the printed scorecard has it.
POINTS_DIVISOR = 10


def _line(text: str | None) -> str:
    return " ".join(text.split()) if text else ""


def system_evidence(row: dict) -> str:
    """The text of a competency's Evidence / Verification column from what the system wrote: the
    scorecard evidence when it wrote one, else the evidence summary (or the reason) it gave, then
    what to verify. Empty for a competency that was not assessed."""
    if row.get("rating") is None:
        return ""
    lead = _line(row.get("scorecard_evidence")) or _line(row.get("evidence")) or _line(row.get("rationale"))
    verify = _line(row.get("verify"))
    # The scorecard evidence already ends with what to verify, so it is not added twice.
    if verify and not _line(row.get("scorecard_evidence")):
        return f"{lead} To verify: {verify}".strip()
    return lead


def build_scorecard(
    *,
    report: dict | None,
    practical: dict | None,
    admin: dict | None,
    top_strengths: list[str],
    panel_decision: str | None,
    total: int | None,
    hidden: bool,
    show_summary: bool = True,
) -> dict | None:
    """The scorecard to show, or None for an interview without competencies (no scoring profile).

    ``report`` is the weighted report as shown (a reviewed rating is already in it), ``total`` the
    total shown (a reviewed or typed one), ``admin`` the hand-filled fields of the latest review.
    With ``hidden`` (the job's switch has scores off) the points and totals are left out; the ratings,
    the evidence, the strengths and the decision stay. With ``show_summary`` false (the job's
    Evaluation Summary switch) the practical case rating, the strengths and the decision are left
    out for every reader; what an admin filled in stays stored."""
    if not report or not report.get("rows"):
        return None
    admin = admin or {}
    written = admin.get("evidence") or {}
    rows = []
    for row in report["rows"]:
        rating = row.get("rating")
        rows.append(
            {
                "name": row["name"],
                "weight": row["weight"],
                "key": bool(row.get("key")),
                "rating": rating,
                "points": None
                if hidden or rating is None
                else round(rating * row["weight"] / POINTS_DIVISOR, 2),
                "evidence": _line(written.get(row["name"])) or system_evidence(row),
            }
        )
    earned = [row["points"] for row in rows if row["points"] is not None]
    max_points = round(sum(row["weight"] for row in rows) / 2, 2)
    practical_rating = admin.get("practical_rating")
    if practical_rating is None and practical and practical.get("complete") and not hidden:
        practical_rating = practical.get("score")
    if hidden or not show_summary:
        practical_rating = None
    strengths = [line.strip() for line in (admin.get("strengths") or "").splitlines() if line.strip()]
    strengths = strengths or [item for item in top_strengths if item]
    return {
        "rows": rows,
        "total_points": None if hidden or not earned else round(sum(earned), 2),
        "max_points": max_points,
        "total_score": None if hidden else total,
        "practical_rating": practical_rating,
        "strengths": strengths if show_summary else [],
        "decision": (_line(admin.get("decision")) or None) if show_summary else None,
        "panel_decision": panel_decision if show_summary else None,
        "hidden": hidden,
        "show_summary": show_summary,
    }
