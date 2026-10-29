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
