"""The rules for a job's strict-interview question list, as plain functions with no database.

Limits come from settings (docs/08_DECISIONS.md): the employer sets 5 questions by default and at
most 6, and the whole interview is capped at 20 minutes, so the answer times of the list must
fit inside that cap. Times are in seconds, in steps of 30, from 30 seconds to 10 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

MIN_QUESTION_CHARS = 10
MAX_QUESTION_CHARS = 500
MIN_SECONDS = 30
MAX_SECONDS = 600
STEP_SECONDS = 30


def max_total_seconds() -> int:
    """The whole interview's cap, which the answer times of the list must fit inside."""
    return settings.strict_interview_max_minutes * 60


@dataclass(frozen=True)
class QuestionDraft:
    """One question and its answer time, before it is saved."""

    text: str
    time_limit_seconds: int


def clean_text(text: str) -> str:
    """A question as one tidy line or paragraph: trimmed, with runs of blanks collapsed."""
    return " ".join(text.split())


def snap_seconds(seconds: int) -> int:
    """A time as a whole number of 30 second steps, inside the allowed range."""
    snapped = round(seconds / STEP_SECONDS) * STEP_SECONDS
    return max(MIN_SECONDS, min(MAX_SECONDS, snapped))


def problems_with(questions: list[QuestionDraft]) -> list[str]:
    """What is wrong with a list the employer wants to save, in words they can act on.

    An empty list is fine: it clears the questions. Each message names the problem and, where
    it helps, the limit.
    """
    found: list[str] = []
    limit = settings.strict_interview_max_questions
    if len(questions) > limit:
        found.append(f"An interview can have at most {limit} questions.")

    for number, question in enumerate(questions, start=1):
        length = len(clean_text(question.text))
        if length < MIN_QUESTION_CHARS:
            found.append(f"Question {number} is too short to be a question.")
        elif length > MAX_QUESTION_CHARS:
            found.append(
                f"Question {number} is too long. Keep it under {MAX_QUESTION_CHARS} characters."
            )
        if not MIN_SECONDS <= question.time_limit_seconds <= MAX_SECONDS:
            found.append(
                f"Question {number} needs between {MIN_SECONDS} seconds and "
                f"{MAX_SECONDS // 60} minutes to answer."
            )

    total = sum(question.time_limit_seconds for question in questions)
    cap = max_total_seconds()
    if total > cap:
        found.append(
            f"The answer times add up to {_minutes(total)}, but the whole interview is limited "
            f"to {_minutes(cap)}. Shorten some of the times."
        )
    return found


def tidy_drafted(raw: list[tuple[str, int]], count: int) -> list[QuestionDraft]:
    """Turn what the AI drafted into a list that is safe to show and save.

    Cleans each question, drops blank, too short and repeated ones, keeps at most ``count``,
    snaps each time to a valid step, and if the times add up to more than the interview allows,
    shortens them evenly (never below the minimum) until they fit. The AI is asked to follow
    these limits, but its output is checked here and never trusted.
    """
    seen: set[str] = set()
    kept: list[QuestionDraft] = []
    for text, seconds in raw:
        cleaned = clean_text(text)
        key = cleaned.casefold()
        if len(cleaned) < MIN_QUESTION_CHARS or key in seen:
            continue
        seen.add(key)
        kept.append(
            QuestionDraft(cleaned[:MAX_QUESTION_CHARS], snap_seconds(int(seconds)))
        )
        if len(kept) == count:
            break
    return _fit_to_cap(kept)


def _fit_to_cap(questions: list[QuestionDraft]) -> list[QuestionDraft]:
    """Shorten the longest times, one step at a time, until the list fits the interview cap."""
    times = [question.time_limit_seconds for question in questions]
    cap = max_total_seconds()
    while sum(times) > cap:
        longest = max(range(len(times)), key=lambda index: times[index])
        if times[longest] <= MIN_SECONDS:
            break  # every question is already at the minimum: nothing more can be shortened
        times[longest] -= STEP_SECONDS
    return [
        QuestionDraft(question.text, seconds)
        for question, seconds in zip(questions, times, strict=True)
    ]


def _minutes(seconds: int) -> str:
    """40 as '40 seconds', 1200 as '20 minutes', 90 as '1 minute 30 seconds'."""
    whole, rest = divmod(seconds, 60)
    parts = []
    if whole:
        parts.append(f"{whole} minute{'s' if whole != 1 else ''}")
    if rest:
        parts.append(f"{rest} second{'s' if rest != 1 else ''}")
    return " ".join(parts) or "0 seconds"
