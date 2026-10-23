"""The pure rules for a job's strict-interview question list (no database)."""

import pytest

from app.core.config import settings
from app.modules.interviews import question_rules as rules
from app.modules.interviews.question_rules import (
    QuestionDraft,
    problems_with,
    snap_seconds,
    tidy_drafted,
)

GOOD = "Tell us about a time you lost a sale and what you learned from it."


def q(text=GOOD, seconds=120):
    return QuestionDraft(text, seconds)


def test_the_limits_come_from_the_decisions():
    assert rules.max_total_seconds() == 20 * 60
    assert settings.strict_interview_default_questions == 5
    assert settings.strict_interview_max_questions == 6


@pytest.mark.parametrize(
    ("given", "expected"),
    [(10, 30), (30, 30), (44, 30), (46, 60), (100, 90), (121, 120), (599, 600), (900, 600), (-5, 30)],
)
def test_a_time_snaps_to_a_30_second_step_inside_the_range(given, expected):
    assert snap_seconds(given) == expected


# --- what the employer may save ------------------------------------------------------------


def test_a_good_list_has_no_problems_and_an_empty_list_is_allowed():
    assert problems_with([q(), q("Why do you want this role at our company?", 90)]) == []
    assert problems_with([]) == []  # clearing the questions is fine


def test_more_questions_than_the_limit_is_refused():
    problems = problems_with([q() for _ in range(7)])

    assert any("at most 6 questions" in problem for problem in problems)


def test_exactly_the_limit_is_allowed_when_the_times_fit():
    assert problems_with([q(seconds=180) for _ in range(6)]) == []  # 18 minutes


def test_a_too_short_or_too_long_question_is_named_by_its_number():
    problems = problems_with([q(), q("Why?"), q("x" * 501)])

    assert "Question 2 is too short to be a question." in problems
    assert any(p.startswith("Question 3 is too long") for p in problems)
    assert not any("Question 1" in p for p in problems)


def test_blanks_do_not_count_towards_the_length():
    assert problems_with([q("   Why     do you want    this     role?   ")]) == []
    assert problems_with([q("          a          ")]) != []


@pytest.mark.parametrize("seconds", [0, 29, 601, 5000])
def test_a_time_outside_the_range_is_refused(seconds):
    problems = problems_with([q(seconds=seconds)])

    assert any("Question 1 needs between 30 seconds and 10 minutes" in p for p in problems)


def test_times_that_add_up_to_more_than_the_interview_allows_are_refused_in_words():
    problems = problems_with([q(seconds=300), q(seconds=300), q(seconds=300), q(seconds=300), q(seconds=120)])

    [message] = [p for p in problems if "add up" in p]
    assert "22 minutes" in message and "limited to 20 minutes" in message


def test_times_that_add_up_to_exactly_the_cap_are_allowed():
    assert problems_with([q(seconds=300) for _ in range(4)]) == []  # 20 minutes


def test_the_cap_follows_the_setting(monkeypatch):
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 10)

    assert any("limited to 10 minutes" in p for p in problems_with([q(seconds=300), q(seconds=360)]))


# --- tidying what the AI drafted -----------------------------------------------------------


def test_drafted_questions_are_cleaned_and_their_times_snapped():
    drafted = tidy_drafted([("  Tell   us about a   project you led.  ", 100), (GOOD, 130)], count=5)

    assert drafted == [
        QuestionDraft("Tell us about a project you led.", 90),
        QuestionDraft(GOOD, 120),
    ]


def test_blank_short_and_repeated_questions_are_dropped():
    drafted = tidy_drafted(
        [("", 60), ("Why?", 60), (GOOD, 120), (GOOD.upper(), 90), ("  " + GOOD + "  ", 60)], count=5
    )

    assert [d.text for d in drafted] == [GOOD]


def test_no_more_than_the_asked_for_count_is_kept():
    raw = [(f"Question number {n}: describe how you would handle it.", 90) for n in range(8)]

    assert len(tidy_drafted(raw, count=5)) == 5
    assert len(tidy_drafted(raw, count=1)) == 1


def test_a_very_long_drafted_question_is_cut_to_the_limit():
    [drafted] = tidy_drafted([("a " * 400, 60)], count=5)

    assert len(drafted.text) <= rules.MAX_QUESTION_CHARS


def test_drafted_times_that_do_not_fit_the_interview_are_shortened_evenly_until_they_do():
    raw = [(f"Describe how you handled situation number {n} at work.", 600) for n in range(4)]  # 40 minutes

    drafted = tidy_drafted(raw, count=5)

    assert sum(d.time_limit_seconds for d in drafted) <= rules.max_total_seconds()
    assert max(d.time_limit_seconds for d in drafted) - min(d.time_limit_seconds for d in drafted) <= 30
    assert problems_with(drafted) == []  # what the AI drafted is always something that can be saved


def test_times_are_never_shortened_below_the_minimum(monkeypatch):
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 1)  # an impossible cap for 3 questions
    raw = [(f"Describe how you handled situation number {n} at work.", 120) for n in range(3)]

    drafted = tidy_drafted(raw, count=5)

    assert all(d.time_limit_seconds >= rules.MIN_SECONDS for d in drafted)


def test_an_empty_draft_stays_empty():
    assert tidy_drafted([], count=5) == []
