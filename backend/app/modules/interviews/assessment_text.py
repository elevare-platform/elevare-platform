"""The written assessment the employer reads, built from the scorecard report.

The interview's assessment is stored as one piece of text (``Interview.ai_rationale``), shown as
it is on the employer's screen and on the shared link. This lays the scorecard out in it, in the
order the scorecard asks for: summary, role, recommendation, competency scores with their
evidence, strengths, gaps and risks, claims requiring validation, and follow-up questions for a
human interviewer, then the fixed line that the AI's output is decision support only.
"""

from __future__ import annotations

from app.modules.ai.interview_scorecard import RATING_NAMES

DECISION_SUPPORT_NOTE = (
    "This assessment is decision support only. A qualified human reviewer must consider the "
    "full application, the interview evidence and the role requirements before any recruitment "
    "decision."
)


def _bullets(title: str, items: list[str]) -> str | None:
    if not items:
        return None
    return title + "\n" + "\n".join(f"- {item}" for item in items)


def _competency_line(item: dict) -> str:
    if item["score"] is None:
        head = f"- {item['name']}: not assessed in this interview."
    else:
        head = f"- {item['name']}: {item['score']} of 5 ({RATING_NAMES[item['score']]})."
        if item["coverage"] == "PARTIALLY_ASSESSED":
            head += " Only partly covered."
    parts = [head]
    if item["rationale"]:
        parts.append(item["rationale"])
    if item["evidence"]:
        parts.append(f"Evidence: \"{item['evidence']}\"")
    return " ".join(parts)


def format_assessment(result) -> str:
    """The assessment text for a scored interview. ``result`` is an ``InterviewScoringResult``.
    Parts the model did not return are left out, so an older style reply reads as it always did."""
    sections: list[str | None] = [result.summary]
    if result.role_assessed:
        sections.append(f"Role assessed: {result.role_assessed}")
    if result.recommendation:
        sections.append(f"Overall recommendation: {result.recommendation}")
    if result.competencies:
        sections.append(
            "Competency scores (1 to 5):\n"
            + "\n".join(_competency_line(item) for item in result.competencies)
        )
    sections += [
        _bullets("Strengths:", result.strengths),
        _bullets("Gaps and risks:", result.weaknesses),
        _bullets("Not covered in this interview:", result.missing_evidence),
        _bullets("Contradictions:", result.contradictions),
        _bullets(
            "Claims requiring validation (these are what the candidate said, not verified facts):",
            result.claims_to_verify,
        ),
        _bullets("Candidate-reported, not scored:", result.candidate_reported),
        _bullets("Suggested follow-up questions for a human interviewer:", result.follow_up_questions),
    ]
    if result.competencies or result.recommendation:
        sections.append(DECISION_SUPPORT_NOTE)
    return "\n\n".join(section for section in sections if section)
