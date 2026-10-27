"""The follow-up prompt for the job's follow-up mode (docs/08_DECISIONS.md, item 40): the standard
rules are unchanged without probes; prepared probes are offered to the model in STANDARD mode and
are the only thing it may ask in PROBES_ONLY mode."""

from app.modules.ai.prompts.interview_follow_up import (
    INTERVIEW_FOLLOW_UP_SYSTEM_PROMPT,
    build_interview_follow_up_prompt,
    follow_up_system_prompt,
)

BASE = {"question": "Tell us about a launch.", "answer": "We launched it.", "interview_brief": "Sales."}


def test_without_prepared_probes_the_prompt_is_the_standard_one():
    assert follow_up_system_prompt() == INTERVIEW_FOLLOW_UP_SYSTEM_PROMPT
    assert "<probes>" not in build_interview_follow_up_prompt(**BASE)


def test_prepared_probes_are_listed_as_data_and_may_be_preferred():
    system = follow_up_system_prompt(has_prepared=True)
    user = build_interview_follow_up_prompt(**BASE, prepared_probes=["What was your part?", "How many outlets?"])

    assert system.startswith(INTERVIEW_FOLLOW_UP_SYSTEM_PROMPT)
    assert "use it instead of writing your own" in system
    assert "you may write your own" in system
    assert "<probes>\nWhat was your part?\nHow many outlets?\n</probes>" in user


def test_probes_only_forbids_writing_a_question_of_its_own():
    system = follow_up_system_prompt(has_prepared=True, only_prepared=True)

    assert "ONLY one of the probes listed" in system
    assert "copied exactly as written" in system
    assert "Never write a question of your own" in system
    assert "you may write your own" not in system
