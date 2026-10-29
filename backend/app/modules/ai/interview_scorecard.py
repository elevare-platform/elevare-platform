"""Checks and tidying for the scorecard report the model returns after an interview.

The model is asked for competency ratings from 1 to 5, a recommendation, claims to verify and
follow-up questions (``prompts/interview_scoring.py``). Its reply is never trusted as it comes:
anything that is not of the expected shape is dropped, and a missing or odd part costs only that
part, never the whole assessment. Plain functions, no database and no network.
"""

from __future__ import annotations

from typing import Any

RECOMMENDATIONS = ("Strongly Recommend", "Recommend", "Further Assessment", "Not Recommended")
RATING_NAMES = {1: "Insufficient evidence", 2: "Limited", 3: "Competent", 4: "Strong", 5: "Exceptional"}
COVERAGE = ("FULLY_ASSESSED", "PARTIALLY_ASSESSED", "NOT_ASSESSED")
# What a question asked for: what the candidate has done, or what they would do.
KINDS = ("EXPERIENCE", "HYPOTHETICAL")
CONFIDENCE = ("high", "medium", "low")


def valid_rating(value: Any) -> bool:
    """A rating from 1 to 5 in steps of a half (3.5), given as a whole number or a decimal. A
    boolean, a string or a rating between the steps (3.3) is not one."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return 1 <= value <= 5 and (value * 2) == int(value * 2)


def clean_rating(value: Any) -> int | float | None:
    """The rating as a whole number when it is one (4.0 becomes 4) or a half point (3.5), or None
    when it is not a rating."""
    if not valid_rating(value):
        return None
    return int(value) if value == int(value) else float(value)


def format_rating(value: int | float) -> str:
    """A rating as it is written: ``4`` or ``3.5``."""
    return str(int(value)) if value == int(value) else f"{value:g}"


def rating_name(value: int | float) -> str:
    """What a rating is called. A half point sits between two levels, so it is named for both
    (3.5 is 'Competent to Strong')."""
    whole = int(value)
    if value == whole:
        return RATING_NAMES[whole]
    return f"{RATING_NAMES[whole]} to {RATING_NAMES[whole + 1]}"

MAX_COMPETENCIES = 12  # a scoring profile may have this many; the generic scorecard asks for at most 8
MAX_LIST_ITEMS = 10
MAX_TEXT = 600


def clean_text(value: Any, limit: int = MAX_TEXT) -> str:
    """A short single piece of text: a string, trimmed and cut to ``limit``; anything else is
    an empty string."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def clean_list(value: Any) -> list[str]:
    """A list of short texts: non-strings and blanks dropped, at most ``MAX_LIST_ITEMS``."""
    if not isinstance(value, list):
        return []
    items = [clean_text(item) for item in value]
    return [item for item in items if item][:MAX_LIST_ITEMS]


def clean_recommendation(value: Any) -> str | None:
    """One of the four recommendations, matched without regard to case; None otherwise."""
    if not isinstance(value, str):
        return None
    wanted = " ".join(value.split()).casefold()
    return next((option for option in RECOMMENDATIONS if option.casefold() == wanted), None)


def clean_competencies(value: Any) -> list[dict]:
    """The rated competencies: each with a name, a rating from 1 to 5 in steps of a half (or None
    when it was not assessed), how fully it was covered, a rationale, a short quote and the text for
    the scorecard's Evidence / Verification column. Entries without a name are dropped; a rating
    outside 1 to 5, or between the half steps, becomes None; a competency marked not assessed never
    keeps a rating."""
    if not isinstance(value, list):
        return []
    cleaned = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        name = clean_text(entry.get("name"), 120)
        if not name:
            continue
        score = clean_rating(entry.get("score"))
        coverage = entry.get("coverage")
        coverage = coverage if coverage in COVERAGE else "FULLY_ASSESSED"
        if coverage == "NOT_ASSESSED":
            score = None
        if score is None:
            coverage = "NOT_ASSESSED"  # nothing usable to rate means nothing was assessed
        kind = entry.get("kind")
        confidence = entry.get("confidence")
        cleaned.append(
            {
                "name": name,
                "score": score,
                "coverage": coverage,
                "kind": kind if kind in KINDS else None,
                "rationale": clean_text(entry.get("rationale")),
                # The scorecard's Evidence / Verification column: a few specific, checkable
                # sentences. Empty for a competency that was not assessed.
                "scorecard_evidence": clean_text(entry.get("scorecard_evidence"), 500) if score is not None else "",
                "evidence": clean_text(entry.get("evidence"), 500),
                "ownership": clean_text(entry.get("ownership"), 300),
                "outcome": clean_text(entry.get("outcome"), 300),
                "confidence": confidence if confidence in CONFIDENCE else None,
                "verify": clean_text(entry.get("verify"), 300),
            }
        )
    return cleaned[:MAX_COMPETENCIES]


def score_from_competencies(competencies: list[dict]) -> int | None:
    """The overall score out of 100: the average rating of the competencies that were assessed,
    times 20, rounded. Competencies that were not assessed are left out, never counted as zero.
    None when none was rated (the caller then keeps the model's own overall score)."""
    rated = [item["score"] for item in competencies if item["score"] is not None]
    if not rated:
        return None
    return round(sum(rated) / len(rated) * 20)
