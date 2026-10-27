"""The rules for a job's strict-interview question list, as plain functions with no database.

Limits come from settings (docs/08_DECISIONS.md): the employer sets 5 questions by default, there
is no cap on how many (item 40: only time limits the list), and the whole interview is capped at
20 minutes, so the answer times of the list must fit inside that cap. Times are in seconds, in
steps of 30, from 30 seconds to 10 minutes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings

MIN_QUESTION_CHARS = 10
MAX_QUESTION_CHARS = 500
MIN_SECONDS = 30
MAX_SECONDS = 600
STEP_SECONDS = 30
# The employer's own follow-up probes for one question: one per line, a few short lines.
MAX_PROBES = 6
MAX_PROBE_CHARS = 300
# The time to answer a follow-up on one question: 30 seconds to 5 minutes, in steps of 30.
MIN_FOLLOW_UP_SECONDS = 30
MAX_FOLLOW_UP_SECONDS = 300


# The standard closing question of the assessment scorecard (docs/08_DECISIONS.md, item 31):
# motivation, notice period, earliest start date and compensation expectations are asked at the
# end if the interview has not covered them. One combined question, so it takes one place of the
# employer's limit; the employer can change or remove it like any other question.
CLOSING_QUESTION_TEXT = (
    "Before we finish, please tell us briefly what motivates you to apply for this role, "
    "your notice period, your earliest start date and your compensation expectations."
)
CLOSING_QUESTION_SECONDS = 90


def closing_question() -> dict:
    """The standard closing question, as the screen shows and adds it."""
    return {"text": CLOSING_QUESTION_TEXT, "time_limit_seconds": CLOSING_QUESTION_SECONDS}


def max_total_seconds() -> int:
    """The whole interview's cap, which the answer times of the list must fit inside."""
    return settings.interview_max_duration_minutes * 60


def max_questions() -> int:
    """The most questions that can fit: every one needs at least the shortest answer time. Not a
    limit of its own (there is none on the count), just what the time cap allows."""
    return max_total_seconds() // MIN_SECONDS


@dataclass(frozen=True)
class QuestionDraft:
    """One question and its answer time, before it is saved."""

    text: str
    time_limit_seconds: int
    # The employer's own probes for it, one per line (empty when none).
    probes: str = ""
    # The time to answer a follow-up on it; None is the platform default.
    follow_up_seconds: int | None = None


def clean_probes(probes: str | None) -> list[str]:
    """The probes as a list of tidy lines: trimmed, runs of blanks collapsed, blanks and repeats
    dropped. Does not cut anything that is too long (``problems_with`` reports it)."""
    seen: set[str] = set()
    lines: list[str] = []
    for line in (probes or "").splitlines():
        cleaned = clean_text(line)
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            lines.append(cleaned)
    return lines


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

    for number, question in enumerate(questions, start=1):
        probes = clean_probes(question.probes)
        if len(probes) > MAX_PROBES:
            found.append(f"Question {number} has too many probes. Keep it to {MAX_PROBES}.")
        if any(len(probe) > MAX_PROBE_CHARS for probe in probes):
            found.append(
                f"A probe on question {number} is too long. Keep each under {MAX_PROBE_CHARS} characters."
            )
        follow_up = question.follow_up_seconds
        if follow_up is not None and not MIN_FOLLOW_UP_SECONDS <= follow_up <= MAX_FOLLOW_UP_SECONDS:
            found.append(
                f"The follow-up time on question {number} needs between {MIN_FOLLOW_UP_SECONDS} "
                f"seconds and {MAX_FOLLOW_UP_SECONDS // 60} minutes."
            )
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


def tidy_drafted(
    raw: list[tuple[str, int]], count: int, closing: QuestionDraft | None = None
) -> list[QuestionDraft]:
    """Turn what the AI drafted into a list that is safe to show and save.

    Cleans each question, drops blank, too short and repeated ones, keeps at most ``count``,
    snaps each time to a valid step, and if the times add up to more than the interview allows,
    shortens them evenly (never below the minimum) until they fit. The AI is asked to follow
    these limits, but its output is checked here and never trusted. ``closing``, when given, is
    added last (after the ``count`` limit, and counted in the total time).
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
    if closing is not None and kept:
        kept.append(closing)
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
