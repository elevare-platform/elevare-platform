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


def weighted_lines(weighted: dict) -> list[str]:
    """The weighted score, said plainly, for a job with a scoring profile. An incomplete score is
    never presented as a full one, and carries no band."""
    if not weighted["complete"]:
        missing = ", ".join(weighted["unassessed"])
        return [
            f"INCOMPLETE SCORE: {weighted['points']:g} of {weighted['assessed_weight']} weighted points "
            f"could be assessed (not assessed: {missing}). No full score and no band are given. "
            "A person decides whether more evidence is needed."
        ]
    lines = [
        f"Weighted score: {weighted['score']} of 100. Suggested band (provisional): {weighted['band']}."
    ]
    if weighted["key_flags"]:
        flagged = ", ".join(weighted["key_flags"])
        lines.append(
            f"Key competency rated under {weighted['key_min_rating']} of 5: {flagged}. "
            "The band is held at Hold for evidence until a person has looked at it."
        )
    return lines


def _competency_line(item: dict) -> str:
    weight = f" (weight {item['weight']}%{', key' if item.get('key') else ''})" if item.get("weight") else ""
    if item["score"] is None:
        head = f"- {item['name']}{weight}: not assessed in this interview."
    else:
        head = f"- {item['name']}{weight}: {item['score']} of 5 ({RATING_NAMES[item['score']]})."
        if item["coverage"] == "PARTIALLY_ASSESSED":
            head += " Only partly covered."
    parts = [head]
    if item.get("kind") == "HYPOTHETICAL":
        parts.append("A plan for a situation, not experience of carrying one out.")
    if item["rationale"]:
        parts.append(item["rationale"])
    if item["evidence"]:
        parts.append(f"Evidence: \"{item['evidence']}\"")
    if item.get("ownership"):
        parts.append(f"Own part: {item['ownership']}")
    if item.get("outcome"):
        parts.append(f"Result: {item['outcome']}")
    if item.get("confidence"):
        parts.append(f"Confidence in this rating: {item['confidence']}.")
    if item.get("verify"):
        parts.append(f"To verify: {item['verify']}")
    return " ".join(parts)


def format_assessment(result) -> str:
    """The assessment text for a scored interview. ``result`` is an ``InterviewScoringResult``.
    Parts the model did not return are left out, so an older style reply reads as it always did."""
    sections: list[str | None] = [result.summary]
    if result.role_assessed:
        sections.append(f"Role assessed: {result.role_assessed}")
    weighted = getattr(result, "weighted", None)
    if weighted:
        # With a scoring profile the band replaces the four-word recommendation.
        sections.append("\n".join(weighted_lines(weighted)))
    elif result.recommendation:
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
        _bullets(
            "Interview conditions to consider (a reassessment may be needed; none of this counts against the candidate):",
            result.technical_flags,
        ),
        _bullets("Candidate-reported, not scored:", result.candidate_reported),
        _bullets("Suggested follow-up questions for a human interviewer:", result.follow_up_questions),
    ]
    if result.competencies or result.recommendation or weighted:
        sections.append(DECISION_SUPPORT_NOTE)
    return "\n\n".join(section for section in sections if section)
