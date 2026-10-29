"""Working an interview's total and band out again from the ratings already saved
(docs/08_DECISIONS.md, item 63).

A scored interview keeps the scoring profile's weights, key marks and band cut-offs as they were
when it was scored. When the profile is changed afterwards, an Elevare admin can have the saved
ratings weighed again under the current profile, with no new model call and no change to any rating.
These functions are the pure part: no database.
"""

from __future__ import annotations

import re

from app.modules.interviews.assessment_text import weighted_lines
from app.modules.interviews.scoring_profile import weighted_report

# The keys weighted_report() produces; everything else in a stored report (the practical case, the
# assessment record, an earlier recalculation) is carried over untouched.
WEIGHTED_KEYS = (
    "rows",
    "points",
    "assessed_weight",
    "total_weight",
    "complete",
    "score",
    "band",
    "bands",
    "key_min_rating",
    "key_flags",
    "unassessed",
)

_WEIGHTED_LINES = re.compile(r"^(Weighted score:|INCOMPLETE SCORE:|Key competency rated under ).*$", re.MULTILINE)
_BLANKS = re.compile(r"\n{3,}")


def recalculate(report: dict, competencies: list[dict], bands: dict | None, key_min_rating: int) -> dict | None:
    """The stored ``report`` weighed again under the profile's current competencies, bands and key
    rule, or None for a report with no competency rows (nothing to weigh).

    Each competency of the profile takes the rating the saved row of the same name has; one the saved
    report does not have is not assessed (so the score becomes incomplete, as it would be), and a
    saved competency the profile no longer has is dropped. The ratings, evidence and the practical
    case are unchanged."""
    saved = {row["name"].casefold(): row for row in report.get("rows") or []}
    if not saved:
        return None
    rows = []
    for competency in competencies:
        old = saved.get(competency["name"].casefold())
        rating = old.get("rating") if old else None
        rows.append(
            {
                **(old or {}),
                "name": competency["name"],
                "weight": competency["weight"],
                "key": bool(competency.get("key")),
                "rating": rating,
                "coverage": (old or {}).get("coverage") if rating is not None else "NOT_ASSESSED",
            }
        )
    fresh = weighted_report(rows, bands, key_min_rating)
    return {**{k: v for k, v in report.items() if k not in WEIGHTED_KEYS}, **fresh}


def retarget_text(text: str | None, report: dict) -> str | None:
    """The written assessment with its score, band and key-competency lines, and the weight and key
    mark in each competency's heading, brought into line with ``report``. The rest of the text is the
    model's and is left as it is."""
    if not text:
        return text
    new_lines = "\n".join(weighted_lines(report))
    placed = False

    def replace(_match: re.Match) -> str:
        nonlocal placed
        if placed:
            return ""
        placed = True
        return new_lines

    out = _WEIGHTED_LINES.sub(replace, text)
    for row in report["rows"]:
        weight = f" (weight {row['weight']}%{', key' if row.get('key') else ''})" if row.get("weight") else ""
        heading = re.compile(rf"^- {re.escape(row['name'])}(?: \(weight \d+%(?:, key)?\))?:", re.MULTILINE)
        out = heading.sub(lambda _m, w=weight, n=row["name"]: f"- {n}{w}:", out, count=1)
    return _BLANKS.sub("\n\n", out).strip("\n")
