"""Switching an interview's score and provisional band off for a job (docs/08_DECISIONS.md, item 54).

When a job's switch is off, its employer and the shared link are not sent the total score, the
provisional band, the practical case's total, or the lines of the written assessment that state them.
The 1 to 5 rating of each competency, the strengths, the gaps and the transcript are still sent: the
switch hides the headline numbers and the suggestion, not the evidence. An Elevare administrator
always gets the real values, so a score can still be reviewed. This is the one place that decides
what is left out, so the employer's screen and the shared link agree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Lines of the written assessment that state a score, a band or a recommendation. A line is dropped
# whole. "Key competency rated under ..." is dropped only when it says the band is held, since it
# otherwise describes a rating.
_SCORE_LINES = re.compile(
    r"^(Weighted score:|INCOMPLETE SCORE:|Overall recommendation:|Practical case:).*$", re.MULTILINE
)
_HELD_LINE = re.compile(r"^Key competency rated under .*The band is held at Hold for evidence.*$", re.MULTILINE)
_BLANKS = re.compile(r"\n{3,}")


@dataclass
class Hidden:
    """An interview's screen with its scores and band left out."""

    score: None
    rationale: str | None
    report: dict | None
    practical: dict | None


def strip_score_lines(text: str | None) -> str | None:
    """The written assessment without the lines that state the total, the band, the practical case's
    score or the overall recommendation."""
    if not text:
        return text
    cleaned = _HELD_LINE.sub("", _SCORE_LINES.sub("", text))
    return _BLANKS.sub("\n\n", cleaned).strip("\n")


# The score number switch (decision item 61) hides the numbers and keeps the band. The total is
# dropped from "Weighted score: 75 of 100. Suggested band (provisional): Shortlist." leaving the band
# half, and the practical case's total and the incomplete score's point counts go whole.
_TOTAL_PREFIX = re.compile(r"^Weighted score: \d+ of 100\. (?=Suggested band)", re.MULTILINE)
_NUMBER_LINES = re.compile(r"^(INCOMPLETE SCORE:|Practical case:).*$", re.MULTILINE)
# The "Gaps and risks:" block: its heading and the "- ..." lines under it.
_GAPS_BLOCK = re.compile(r"^Gaps and risks:\n(?:- .*(?:\n|$))*", re.MULTILINE)


def strip_gaps(text: str | None) -> str | None:
    """The written assessment without its "Gaps and risks:" block."""
    if not text:
        return text
    return _BLANKS.sub("\n\n", _GAPS_BLOCK.sub("", text)).strip("\n")


def strip_numbers(text: str | None) -> str | None:
    """The written assessment without the total score or the practical case's score; the suggested
    band and the 1 to 5 ratings stay."""
    if not text:
        return text
    cleaned = _NUMBER_LINES.sub("", _TOTAL_PREFIX.sub("", text))
    return _BLANKS.sub("\n\n", cleaned).strip("\n")


def hide_numbers(*, rationale: str | None, report: dict | None, practical: dict | None) -> Hidden:
    """The weighted report, the practical case and the written assessment with the NUMBERS left out
    and the band kept: no total, no points, no cut-offs, no practical total. Each competency's 1 to 5
    rating stays. The report is flagged ``number_hidden`` so the screen draws the band without a
    total or a points column."""
    hidden_report = None
    if report is not None:
        hidden_report = {
            **report,
            "number_hidden": True,
            "score": None,
            "points": 0.0,
            "bands": {},
        }
    hidden_practical = None
    if practical is not None:
        hidden_practical = {**practical, "number_hidden": True, "score": None}
    return Hidden(
        score=None,
        rationale=strip_numbers(rationale),
        report=hidden_report,
        practical=hidden_practical,
    )


def hide_scores(*, rationale: str | None, report: dict | None, practical: dict | None) -> Hidden:
    """The weighted report, the practical case and the written assessment with the scores and band
    left out. The report keeps its rows (competency, weight, rating) and is flagged ``hidden`` so the
    screen shows no total, no band and no 'incomplete score' notice; the cut-offs are not sent."""
    hidden_report = None
    if report is not None:
        hidden_report = {
            **report,
            "hidden": True,
            "score": None,
            "band": None,
            "points": 0.0,
            "bands": {},
            "reviewed": False,
        }
    hidden_practical = None
    if practical is not None:
        hidden_practical = {**practical, "hidden": True, "score": None}
    return Hidden(
        score=None,
        rationale=strip_score_lines(rationale),
        report=hidden_report,
        practical=hidden_practical,
    )
