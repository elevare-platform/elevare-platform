"""The practical case: a realistic scenario the candidate works through aloud, scored separately
(docs/08_DECISIONS.md, item 43; docs/16_COLTON_BRIEF.md, Section 6).

The client's framework scores a practical exercise on the same 1 to 5 anchors as everything else,
across five criteria with fixed weights, and reports it as a separate validation score out of 5:
it is NEVER added to the 100-point competency score. The case score is worked out here from the
ratings the model gives each criterion, as the weighted score is, so it always agrees with the
table the employer reads. A criterion the model could not rate makes the case score incomplete (no
number), never a low one.
"""

from __future__ import annotations

from typing import Any

MIN_RATING = 1
MAX_RATING = 5

# The client's evaluation split: prioritisation, commercial realism, measurement, risk and
# contingency, clarity of communication (30, 25, 20, 15, 10). "Realism" is the client's "commercial
# realism" worded so that it also fits roles that are not commercial.
CRITERIA = [
    {
        "key": "prioritisation",
        "name": "Prioritisation",
        "weight": 30,
        "means": "what comes first and why, with sensible sequencing and trade-offs",
    },
    {
        "key": "realism",
        "name": "Realism",
        "weight": 25,
        "means": "assumptions, numbers and resources that would hold in the real business, with the assumptions stated",
    },
    {
        "key": "measurement",
        "name": "Measurement",
        "weight": 20,
        "means": "the measures, targets and reports that would show whether the plan is working",
    },
    {
        "key": "risk",
        "name": "Risk and contingency",
        "weight": 15,
        "means": "what could go wrong, what would trigger a change of plan, and what to do then",
    },
    {
        "key": "clarity",
        "name": "Clarity of communication",
        "weight": 10,
        "means": "an answer a leader could follow and act on: structured and specific",
    },
]


def _rating(value: Any) -> int | None:
    """A rating the model gave, if it is a whole number from 1 to 5; anything else is no rating."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if MIN_RATING <= value <= MAX_RATING else None


def report(raw: Any, question_number: int) -> dict:
    """The practical case report for the question numbered ``question_number``.

    ``raw`` is what the model returned for it (``{"criteria": [{"key", "rating", "rationale"}],
    "summary"}``, or anything at all if it returned nothing usable). One row per criterion in the
    client's order; a criterion with no valid rating is not assessed. ``score`` is out of 5 with one
    decimal and is None unless every criterion was rated (``complete``)."""
    given = {}
    for item in (raw.get("criteria") if isinstance(raw, dict) else None) or []:
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            given[item["key"].strip().casefold()] = item
    rows = []
    for criterion in CRITERIA:
        item = given.get(criterion["key"], {})
        rationale = item.get("rationale")
        rows.append(
            {
                "key": criterion["key"],
                "name": criterion["name"],
                "weight": criterion["weight"],
                "rating": _rating(item.get("rating")),
                "rationale": " ".join(rationale.split()) if isinstance(rationale, str) else "",
            }
        )
    assessed = [row for row in rows if row["rating"] is not None]
    complete = len(assessed) == len(rows)
    total_weight = sum(row["weight"] for row in rows)
    summary = raw.get("summary") if isinstance(raw, dict) else None
    return {
        "question_number": question_number,
        "rows": rows,
        "complete": complete,
        "score": round(sum(row["rating"] * row["weight"] for row in rows) / total_weight, 1) if complete else None,
        "assessed_weight": sum(row["weight"] for row in assessed),
        "total_weight": total_weight,
        "unassessed": [row["name"] for row in rows if row["rating"] is None],
        "summary": " ".join(summary.split()) if isinstance(summary, str) else "",
    }
