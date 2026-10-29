"""Scoring profiles: competencies with weights, and the weighted score they give.

A job's strict interview may carry a scoring profile (docs/08_DECISIONS.md, items 33 and 36; the
Colton Group framework, docs/16_COLTON_BRIEF.md sections 3 and 4): a short list of competencies,
each with a weight, the weights adding up to 100. The AI rates each competency from 1 to 5; the
score is worked out HERE from those ratings:

    points of a competency = rating / 5 x weight        total = the sum, out of 100

A competency that could not be assessed is never left out and never counted as zero: the score is
INCOMPLETE ("60 of 75 points assessed"), no full score and no band is given, and a human decides.
A band is a label on the total (provisional: the client's thresholds are not validated), and a key
competency rated under the minimum caps the band at "Hold for evidence". Plain functions, no
database and no network.
"""

from __future__ import annotations

from typing import Any

from app.modules.ai.interview_scorecard import clean_rating

MIN_COMPETENCIES = 2
MAX_COMPETENCIES = 12
MAX_NAME_CHARS = 80
MIN_RATING, MAX_RATING = 1, 5

BAND_STRONG = "Strong shortlist"
BAND_SHORTLIST = "Shortlist"
BAND_HOLD = "Hold for evidence"
BAND_NOT = "Do not shortlist"

DEFAULT_BANDS = {"strong": 85, "shortlist": 75, "hold": 65}
DEFAULT_KEY_MIN_RATING = 3

# The client's three role profiles (the Colton Group brief, section 3): the weights are theirs, the
# two highest-weighted competencies of each role are the key ones (their minimum-rating rule).
TEMPLATES = [
    {
        "code": "commercial_director",
        "title": "Commercial Director",
        "competencies": [
            {"name": "Commercial strategy and profitable growth", "weight": 25, "key": True},
            {"name": "P&L, pricing and financial management", "weight": 20, "key": True},
            {"name": "Route-to-market and distribution strategy", "weight": 20, "key": False},
            {"name": "Leadership and organisational development", "weight": 15, "key": False},
            {"name": "Brand and portfolio management", "weight": 10, "key": False},
            {"name": "Cross-functional execution", "weight": 10, "key": False},
        ],
    },
    {
        "code": "national_sales_manager",
        "title": "National Sales Manager",
        "competencies": [
            {"name": "Route-to-market and distributor development", "weight": 30, "key": True},
            {"name": "Sales execution and territory management", "weight": 25, "key": True},
            {"name": "Sales-force leadership", "weight": 15, "key": False},
            {"name": "Revenue, margin and collections management", "weight": 15, "key": False},
            {"name": "Forecasting and supply coordination", "weight": 10, "key": False},
            {"name": "Reporting and performance analytics", "weight": 5, "key": False},
        ],
    },
    {
        "code": "senior_marketing_manager",
        "title": "Senior Marketing Manager",
        "competencies": [
            {"name": "Brand strategy and positioning", "weight": 25, "key": True},
            {"name": "Consumer insights and market research", "weight": 20, "key": True},
            {"name": "Product launches and integrated campaigns", "weight": 20, "key": False},
            {"name": "Marketing budget and ROI", "weight": 15, "key": False},
            {"name": "Agency and stakeholder management", "weight": 10, "key": False},
            {"name": "Sales alignment and launch readiness", "weight": 10, "key": False},
        ],
    },
]


def clean_name(value: Any) -> str:
    """A competency name as one tidy line (trimmed, blanks collapsed); '' if it is not text."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def problems_with(
    competencies: list[dict], bands: dict | None = None, key_min_rating: int = DEFAULT_KEY_MIN_RATING
) -> list[str]:
    """What is wrong with a profile the employer wants to save, in words they can act on. An
    empty list means it can be saved."""
    found: list[str] = []
    if not MIN_COMPETENCIES <= len(competencies) <= MAX_COMPETENCIES:
        found.append(
            f"A scoring profile needs between {MIN_COMPETENCIES} and {MAX_COMPETENCIES} competencies."
        )
    seen: set[str] = set()
    total = 0
    for number, item in enumerate(competencies, start=1):
        name = clean_name(item.get("name"))
        weight = item.get("weight")
        if not name:
            found.append(f"Competency {number} needs a name.")
        elif len(name) > MAX_NAME_CHARS:
            found.append(f"Competency {number} has a name over {MAX_NAME_CHARS} characters.")
        elif name.casefold() in seen:
            found.append(f"\"{name}\" is listed twice.")
        seen.add(name.casefold())
        if not isinstance(weight, int) or isinstance(weight, bool) or not 1 <= weight <= 100:
            found.append(f"Competency {number} needs a whole-number weight from 1 to 100.")
        else:
            total += weight
    if len(competencies) >= MIN_COMPETENCIES and total != 100:
        found.append(f"The weights add up to {total}%, and must add up to 100%.")
    if not MIN_RATING <= key_min_rating <= MAX_RATING:
        found.append("The minimum rating for key competencies must be from 1 to 5.")
    if bands is not None:
        strong, shortlist, hold = bands.get("strong"), bands.get("shortlist"), bands.get("hold")
        values = (strong, shortlist, hold)
        if any(not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= 100 for v in values):
            found.append("The band thresholds must be whole numbers from 1 to 100.")
        elif not strong > shortlist > hold:
            found.append("The band thresholds must go down: Strong shortlist, then Shortlist, then Hold.")
    return found


def tidy(competencies: list[dict]) -> list[dict]:
    """The competencies as stored: clean names, integer weights, a key flag on each."""
    return [
        {"name": clean_name(item["name"]), "weight": int(item["weight"]), "key": bool(item.get("key"))}
        for item in competencies
    ]


def normalise(rated: list[dict], profile: list[dict]) -> list[dict]:
    """Line the model's ratings up with the profile: one row per profile competency, in the
    profile's order, named as the profile names it. A rating for a name the profile does not have
    is dropped; a competency the model did not rate is not assessed. Ratings outside 1 to 5 are
    not assessed either: nothing usable is never a zero."""
    by_name = {clean_name(item.get("name")).casefold(): item for item in rated or []}
    rows = []
    for competency in profile:
        item = by_name.get(competency["name"].casefold(), {})
        # A rating from 1 to 5 in steps of a half; anything else is not assessed.
        rating = clean_rating(item.get("score"))
        usable = rating is not None
        rows.append(
            {
                "name": competency["name"],
                "weight": competency["weight"],
                "key": bool(competency.get("key")),
                "rating": rating,
                "coverage": item.get("coverage") if usable else "NOT_ASSESSED",
                "rationale": item.get("rationale", ""),
                "scorecard_evidence": item.get("scorecard_evidence", "") if usable else "",
                "evidence": item.get("evidence", ""),
                "kind": item.get("kind"),
                "ownership": item.get("ownership", ""),
                "outcome": item.get("outcome", ""),
                "confidence": item.get("confidence"),
                "verify": item.get("verify", ""),
            }
        )
    return rows


def weighted_report(
    rows: list[dict],
    bands: dict | None = None,
    key_min_rating: int = DEFAULT_KEY_MIN_RATING,
) -> dict:
    """The weighted score of ``rows`` (from ``normalise``), as a report to store and show.

    ``points`` is what was earned out of ``assessed_weight`` (the weight of the competencies that
    were rated) and ``total_weight`` is 100. ``complete`` is true only when every competency was
    rated; then ``score`` is the total, rounded, and ``band`` the label. Otherwise ``score`` and
    ``band`` are None. ``key_flags`` names the key competencies rated under the minimum; a flag
    caps the band at "Hold for evidence"."""
    bands = bands or DEFAULT_BANDS
    assessed = [row for row in rows if row["rating"] is not None]
    points = sum(row["rating"] / MAX_RATING * row["weight"] for row in assessed)
    assessed_weight = sum(row["weight"] for row in assessed)
    total_weight = sum(row["weight"] for row in rows)
    complete = len(assessed) == len(rows) and bool(rows)
    key_flags = [
        row["name"] for row in assessed if row["key"] and row["rating"] < key_min_rating
    ]
    unassessed = [row["name"] for row in rows if row["rating"] is None]
    score = round(points) if complete else None
    band = band_for(score, bands, capped=bool(key_flags)) if complete else None
    return {
        "rows": rows,
        "points": round(points, 1),
        "assessed_weight": assessed_weight,
        "total_weight": total_weight,
        "complete": complete,
        "score": score,
        "band": band,
        "bands": bands,
        "key_min_rating": key_min_rating,
        "key_flags": key_flags,
        "unassessed": unassessed,
    }


def band_for(score: int, bands: dict, *, capped: bool = False) -> str:
    """The label for a total. ``capped`` (a key competency under its minimum) never lets the band
    be better than Hold for evidence, and never makes it worse than the total alone would."""
    if score >= bands["strong"]:
        label = BAND_STRONG
    elif score >= bands["shortlist"]:
        label = BAND_SHORTLIST
    elif score >= bands["hold"]:
        label = BAND_HOLD
    else:
        label = BAND_NOT
    if capped and label in (BAND_STRONG, BAND_SHORTLIST):
        return BAND_HOLD
    return label
