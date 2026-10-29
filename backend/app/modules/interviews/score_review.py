"""A reviewed interview score (docs/08_DECISIONS.md, item 52).

An Elevare admin can change the competency ratings of a finished interview and/or set its total in
place of the ones the system worked out. The total follows the ratings by the system's own formula
unless the admin typed one, the band follows the total by the job's own cut-offs, a small "Reviewed"
tag is shown beside it on the employer's screen and on the shared link, and the system's own result is
kept with who changed it and when. These functions are the one place that works out what is shown, so
every screen and the shared link agree.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.ai.interview_scorecard import (
    clean_rating,
    format_rating,
    rating_name,
    valid_rating,
)
from app.modules.interviews.assessment_text import weighted_lines
from app.modules.interviews.scoring_profile import MAX_RATING, band_for

MIN_SCORE = 0
MAX_SCORE = 100


@dataclass
class Shown:
    """What an interview's screen shows once a review, if there is one, is applied."""

    score: int | None
    rationale: str | None
    report: dict | None
    reviewed: bool


def reviewed_lines(report: dict, score: int, band: str, key_flags: list[str]) -> list[str]:
    """The weighted-score lines of the written assessment for a reviewed score. The cut-off band is
    named as provisional like the system's own; the 'held at Hold for evidence' sentence is left
    out, because that rule lasts only until a person has looked at it, and a person has."""
    lines = [f"Weighted score: {score} of 100. Suggested band (provisional): {band}."]
    if key_flags:
        lines.append(f"Key competency rated under {report.get('key_min_rating')} of 5: {', '.join(key_flags)}.")
    return lines


def _head(row: dict, rating: int | None) -> str:
    """The first line of a competency's entry in the written assessment, as scoring writes it."""
    weight = f" (weight {row['weight']}%{', key' if row.get('key') else ''})" if row.get("weight") else ""
    if rating is None:
        return f"- {row['name']}{weight}: not assessed in this interview."
    head = f"- {row['name']}{weight}: {format_rating(rating)} of 5 ({rating_name(rating)})."
    if row.get("coverage") == "PARTIALLY_ASSESSED":
        head += " Only partly covered."
    return head




def apply_review(
    *,
    score: int | None,
    rationale: str | None,
    report: dict | None,
    review_score: int | None,
    review_ratings: dict | None = None,
    review_rationale: str | None = None,
) -> Shown:
    """The score, the written assessment and the weighted report to show, given the latest review
    (``None`` for both when there is no review or it was taken away: the system's own result is
    shown unchanged).

    ``review_ratings`` are the competency ratings the reviewer changed, ``{name: 1 to 5}``; they
    replace the system's in the table, and the total is worked out from all the ratings by the
    system's formula. ``review_score`` is a total the reviewer typed, which wins over that. The
    band follows the total by the job's cut-offs, with no cap for a low key competency (the cap
    lasts until a person has looked), the score counts as complete, and the lines of the written
    assessment that carry the total and the changed ratings are replaced so the text agrees with the
    numbers. Without a report (a job with no scoring profile) only a typed total changes anything.

    ``review_rationale`` is a written assessment the reviewer wrote: it is shown as it is, in place of
    the system's text and of any rewriting of its score lines, and it counts as a review on its own
    (the system's text is kept; this does not touch it)."""
    changes = review_ratings or {}
    if review_score is None and not changes:
        if review_rationale:
            return Shown(score=score, rationale=review_rationale, report=report, reviewed=True)
        return Shown(score=score, rationale=rationale, report=report, reviewed=False)

    if not report or "bands" not in report:
        text = review_rationale or rationale
        if review_score is None:
            return Shown(score=score, rationale=text, report=report, reviewed=bool(review_rationale))
        return Shown(score=review_score, rationale=text, report=report, reviewed=True)

    by_name = {name.casefold(): clean_rating(rating) for name, rating in changes.items() if valid_rating(rating)}
    rows = [
        {**row, "rating": by_name.get(row["name"].casefold(), row.get("rating"))}
        for row in report.get("rows", [])
    ]
    assessed = [row for row in rows if row["rating"] is not None]
    points = sum(row["rating"] / MAX_RATING * row["weight"] for row in assessed)
    complete_rows = len(assessed) == len(rows) and bool(rows)
    key_flags = [row["name"] for row in assessed if row.get("key") and row["rating"] < report["key_min_rating"]]

    if review_score is not None:
        total = review_score
    elif complete_rows:
        total = round(points)
    else:
        total = None  # ratings changed but a competency is still not rated: still incomplete

    band = band_for(total, report["bands"], capped=False) if total is not None else None
    shown_report = {
        **report,
        "rows": rows,
        "points": round(points, 1),
        "assessed_weight": sum(row["weight"] for row in assessed),
        "complete": total is not None,
        "score": total,
        "band": band,
        "key_flags": key_flags,
        "unassessed": [row["name"] for row in rows if row["rating"] is None],
        "reviewed": True,
    }

    new_rationale = rationale
    if rationale:
        original = "\n".join(weighted_lines(report))
        if total is not None:
            replacement = "\n".join(reviewed_lines(report, total, band, key_flags))
        else:
            replacement = "\n".join(weighted_lines({**shown_report, "complete": False}))
        if original in new_rationale:
            new_rationale = new_rationale.replace(original, replacement, 1)
        for before, after in zip(report.get("rows", []), rows, strict=False):
            if before.get("rating") != after["rating"]:
                new_rationale = new_rationale.replace(_head(before, before.get("rating")), _head(after, after["rating"]), 1)
    return Shown(score=total, rationale=review_rationale or new_rationale, report=shown_report, reviewed=True)
