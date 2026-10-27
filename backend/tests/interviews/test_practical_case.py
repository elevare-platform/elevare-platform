"""The practical case (docs/08_DECISIONS.md, item 43; docs/16_COLTON_BRIEF.md, Section 6): a scenario
scored on five criteria, reported out of 5 and apart from the weighted score, never added to it."""

import pytest
from sqlalchemy import select

from app.modules.ai.prompts.interview_scoring import (
    build_interview_scoring_prompt,
    describe_practical_case,
)
from app.modules.ai.schema import InterviewScoringResult
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.assessment_text import format_assessment, practical_lines
from app.modules.interviews.models import (
    InterviewWeightedScore,
    JobScoringProfile,
    StrictInterviewRun,
)
from app.modules.interviews.practical_case import CRITERIA, report

from .test_interview_tasks import (
    _mock_anthropic_service,
    _patch_engine_to_use_test_session,
)
from .test_scoring_profile import (
    COMPETENCIES,
    _service_returning,
    rated,
    score,
)
from .test_strict_interview import make_strict

KEYS = [criterion["key"] for criterion in CRITERIA]


def case_reply(*ratings, summary="A workable plan."):
    """What the model returns for the practical case, one rating (or None) per criterion in order."""
    return {
        "criteria": [
            {"key": key, "rating": rating, "rationale": f"Why {key}."} for key, rating in zip(KEYS, ratings, strict=True)
        ],
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# The criteria and the score
# ---------------------------------------------------------------------------


def test_the_five_criteria_are_the_clients_with_weights_adding_up_to_100():
    assert [(c["key"], c["weight"]) for c in CRITERIA] == [
        ("prioritisation", 30),
        ("realism", 25),
        ("measurement", 20),
        ("risk", 15),
        ("clarity", 10),
    ]
    assert sum(c["weight"] for c in CRITERIA) == 100


@pytest.mark.parametrize(
    ("ratings", "expected"),
    [
        ((5, 5, 5, 5, 5), 5.0),
        ((1, 1, 1, 1, 1), 1.0),
        ((4, 4, 4, 4, 4), 4.0),
        ((3, 4, 5, 2, 3), 3.5),  # 3*30 + 4*25 + 5*20 + 2*15 + 3*10 = 350
        ((5, 3, 3, 3, 3), 3.6),  # (150 + 75 + 60 + 45 + 30) / 100
    ],
)
def test_the_case_score_is_the_weighted_average_of_the_ratings_out_of_5(ratings, expected):
    result = report(case_reply(*ratings), 8)

    assert result["complete"] is True and result["score"] == expected
    assert result["question_number"] == 8


def test_a_criterion_not_covered_makes_the_case_incomplete_with_no_score_never_a_low_one():
    result = report(case_reply(4, 4, None, 4, 4), 8)

    assert result["complete"] is False
    assert result["score"] is None
    assert result["unassessed"] == ["Measurement"]
    assert result["assessed_weight"] == 80 and result["total_weight"] == 100


@pytest.mark.parametrize("bad", [0, 6, -1, 4.5, "4", True, None, [4]])
def test_a_rating_that_is_not_a_whole_number_from_1_to_5_is_not_a_rating(bad):
    reply = case_reply(4, 4, 4, 4, 4)
    reply["criteria"][0]["rating"] = bad

    result = report(reply, 8)

    assert result["rows"][0]["rating"] is None and result["complete"] is False


def test_keys_are_matched_without_regard_to_case_and_unknown_keys_are_ignored():
    reply = {"criteria": [{"key": " PRIORITISATION ", "rating": 5}, {"key": "charisma", "rating": 5}]}

    result = report(reply, 3)

    assert result["rows"][0]["rating"] == 5
    assert [row["rating"] for row in result["rows"][1:]] == [None, None, None, None]


@pytest.mark.parametrize("raw", [None, "text", [], {}, {"criteria": "nope"}, {"criteria": [None, 3, "x"]}])
def test_a_reply_with_nothing_usable_is_a_case_with_every_criterion_not_covered(raw):
    result = report(raw, 8)

    assert result["complete"] is False and result["score"] is None
    assert len(result["unassessed"]) == 5


def test_rows_follow_the_clients_order_and_text_is_tidied():
    result = report({"criteria": [{"key": "risk", "rating": 3, "rationale": "  Named   two   risks. "}], "summary": " Fine \n plan. "}, 8)

    assert [row["key"] for row in result["rows"]] == KEYS
    assert result["rows"][3]["rationale"] == "Named two risks."
    assert result["summary"] == "Fine plan."


# ---------------------------------------------------------------------------
# What the model is told, and what scoring returns
# ---------------------------------------------------------------------------


def test_the_prompt_names_the_practical_question_and_the_five_criteria_with_their_keys():
    block = describe_practical_case({"number": 9, "text": "Build a 90-day plan."})

    assert 'Question 9 is the practical case: "Build a 90-day plan."' in block
    for key in KEYS:
        assert f'key "{key}"' in block
    assert "do not give an overall number" in block


def test_without_a_practical_case_the_prompt_says_to_leave_it_out():
    assert "There is no practical case in this interview" in describe_practical_case(None)


def test_the_system_prompt_says_the_case_is_separate_and_never_part_of_the_competencies():
    system, user = build_interview_scoring_prompt(
        interview_brief="b", transcript="t", scoring_rubric="r", practical_question={"number": 2, "text": "A case."}
    )
    text = " ".join(system.split())

    assert "never added to the weighted competency score" in text
    assert "Rate it ONLY in the practical_case field" in text
    assert "not of having carried one out" in text
    assert "PRACTICAL CASE\n==============" in user and "Question 2 is the practical case" in user


@pytest.mark.asyncio
async def test_scoring_reports_the_case_apart_and_the_weighted_total_ignores_it():
    payload = {"summary": "Good.", "competencies": rated(4, 3, 5, 4, 5, 3), "practical_case": case_reply(5, 5, 5, 5, 5)}
    service = _service_returning(payload)

    result = await score(service, practical_question={"number": 8, "text": "A case."})

    assert result.practical["score"] == 5.0 and result.practical["complete"] is True
    assert result.weighted["score"] == 80  # exactly what the same ratings give without a case
    assert result.score == 80


@pytest.mark.asyncio
async def test_a_case_in_the_reply_is_ignored_when_the_interview_has_none():
    payload = {"summary": "Good.", "competencies": rated(4, 3, 5, 4, 5, 3), "practical_case": case_reply(5, 5, 5, 5, 5)}

    result = await score(_service_returning(payload))

    assert result.practical is None


@pytest.mark.asyncio
async def test_a_missing_case_in_the_reply_is_an_incomplete_case_not_a_failure():
    payload = {"summary": "Good.", "competencies": rated(4, 3, 5, 4, 5, 3)}

    result = await score(_service_returning(payload), practical_question={"number": 8, "text": "A case."})

    assert result.failed is False
    assert result.practical["complete"] is False and result.practical["score"] is None


@pytest.mark.asyncio
async def test_the_practical_question_reaches_the_model():
    service = _service_returning({"summary": "x", "competencies": rated(3, 3, 3, 3, 3, 3)})

    await score(service, practical_question={"number": 8, "text": "Build a 90-day plan."})

    sent = service._client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert 'Question 8 is the practical case: "Build a 90-day plan."' in sent


# ---------------------------------------------------------------------------
# The written assessment
# ---------------------------------------------------------------------------


def test_a_complete_case_is_said_with_its_score_the_rows_and_that_it_is_not_part_of_the_score():
    lines = practical_lines(report(case_reply(4, 4, 4, 4, 4, summary="A solid plan."), 8))

    assert lines[0].startswith("Practical case: 4 of 5.") and "not part of the weighted score" in lines[0]
    assert "- Prioritisation (30%): 4 of 5. Why prioritisation." in lines
    assert lines[-1] == "A solid plan."


def test_an_incomplete_case_says_so_and_gives_no_score():
    lines = practical_lines(report(case_reply(4, None, 4, None, 4), 8))

    assert lines[0].startswith("Practical case: INCOMPLETE. 3 of 5 criteria could be rated")
    assert "Realism, Risk and contingency" in lines[0] and "No case score is given" in lines[0]
    assert "- Realism (25%): not covered." in lines


def test_the_assessment_text_carries_the_case_and_the_referee_questions():
    result = InterviewScoringResult(
        score=70,
        summary="Fine.",
        recommendation="Recommend",
        practical=report(case_reply(3, 3, 3, 3, 3), 8),
        reference_check_questions=["What did the candidate personally do on the Lagos launch?"],
    )

    text = format_assessment(result)

    assert "Practical case: 3 of 5." in text
    assert "Questions for referees (to check the major achievements):\n- What did the candidate personally do on the Lagos launch?" in text


def test_nothing_about_a_case_or_referees_is_said_when_there_is_none():
    text = format_assessment(InterviewScoringResult(score=70, summary="Fine.", recommendation="Recommend"))

    assert "Practical case" not in text and "referees" not in text


# ---------------------------------------------------------------------------
# In the scoring task
# ---------------------------------------------------------------------------


async def strict_with_case(db_session, monkeypatch, with_profile=True):
    from unittest.mock import AsyncMock

    from app.modules.interviews import scoring_profile as rules
    from app.modules.interviews.enums import InterviewStatus

    interview = await make_strict(db_session, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    if with_profile:
        db_session.add(
            JobScoringProfile(job_id=interview.job.id, competencies=COMPETENCIES, bands=dict(rules.DEFAULT_BANDS), key_min_rating=3)
        )
    run = (await db_session.execute(select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview.interview.id))).scalar_one()
    run.questions = [
        {"text": "How do you set a strategy?", "time_limit_seconds": 120, "competency": "Strategy"},
        {"text": "Build a 90-day plan for three regions.", "time_limit_seconds": 240, "competency": None, "is_practical": True},
    ]
    await db_session.commit()
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    return interview


@pytest.mark.asyncio
async def test_the_practical_question_is_told_to_the_scorer_and_the_case_is_stored_apart_from_the_weighted_score(
    db_session, monkeypatch
):
    from .test_scoring_profile import scoring_result

    interview = await strict_with_case(db_session, monkeypatch)
    result = scoring_result(4, 3, 5, 4, 5, 3)
    result.practical = report(case_reply(4, 4, 4, 4, 4), 2)
    ai = _mock_anthropic_service(monkeypatch, result=result)

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    assert ai.score_interview_transcript.await_args.kwargs["practical_question"] == {
        "number": 2,
        "text": "Build a 90-day plan for three regions.",
    }
    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 80  # the case adds nothing to it
    [row] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert row.report["score"] == 80 and row.report["practical"]["score"] == 4.0
    assert "Practical case: 4 of 5." in interview.interview.ai_rationale


@pytest.mark.asyncio
async def test_a_job_with_no_scoring_profile_still_gets_its_case_reported(db_session, monkeypatch):
    interview = await strict_with_case(db_session, monkeypatch, with_profile=False)
    result = InterviewScoringResult(score=71, summary="Fine.", practical=report(case_reply(5, 5, 5, 5, 5), 2))
    _mock_anthropic_service(monkeypatch, result=result)

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 71
    [row] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert "rows" not in row.report and row.report["practical"]["score"] == 5.0


@pytest.mark.asyncio
async def test_an_interview_with_no_practical_question_tells_the_scorer_so(db_session, monkeypatch):
    from .test_scoring_profile import scoring_result, strict_with_profile

    interview = await strict_with_profile(db_session, monkeypatch)
    ai = _mock_anthropic_service(monkeypatch, result=scoring_result(4, 3, 5, 4, 5, 3))

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    assert ai.score_interview_transcript.await_args.kwargs["practical_question"] is None
    [row] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert "practical" not in row.report
