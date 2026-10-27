"""A scoring profile built for a job that has none (docs/08_DECISIONS.md, item 42): the draft is
repaired and checked, saved once per job, used for every candidate, and a failure falls back to the
simple scorecard."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.modules.ai.prompts.scoring_profile_draft import (
    SCORING_PROFILE_DRAFT_SYSTEM_PROMPT,
    build_scoring_profile_draft_prompt,
)
from app.modules.interviews import scoring_profile as rules
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.auto_profile import AUTO_CODE, ensure_profile, finalise
from app.modules.interviews.models import InterviewWeightedScore, JobScoringProfile

from .test_interview_tasks import (
    _mock_anthropic_service,
    _patch_engine_to_use_test_session,
)
from .test_scoring_profile import report_for
from .test_strict_interview import make_strict

DRAFT = [
    {"name": "Route-to-market strategy", "weight": 30},
    {"name": "Sales-force leadership", "weight": 25},
    {"name": "Margin and collections management", "weight": 20},
    {"name": "Forecasting and supply coordination", "weight": 15},
    {"name": "Reporting and analytics", "weight": 10},
]


# ---------------------------------------------------------------------------
# Checking and repairing what the model drafted
# ---------------------------------------------------------------------------


def test_a_good_draft_is_kept_with_the_two_heaviest_competencies_as_key():
    profile = finalise(DRAFT)

    assert [(c["name"], c["weight"], c["key"]) for c in profile] == [
        ("Route-to-market strategy", 30, True),
        ("Sales-force leadership", 25, True),
        ("Margin and collections management", 20, False),
        ("Forecasting and supply coordination", 15, False),
        ("Reporting and analytics", 10, False),
    ]
    assert rules.problems_with(profile) == []


@pytest.mark.parametrize("weights", [[40, 30, 20], [33, 33, 33], [1, 1, 1, 1, 1, 1], [50, 30, 20, 10, 10], [7, 7, 7, 7, 7, 7, 7]])
def test_weights_that_do_not_add_up_are_scaled_to_exactly_100_in_whole_numbers(weights):
    profile = finalise([{"name": f"Competency number {n}", "weight": w} for n, w in enumerate(weights)])

    assert profile is not None
    assert sum(c["weight"] for c in profile) == 100
    assert all(isinstance(c["weight"], int) and c["weight"] >= 1 for c in profile)
    assert rules.problems_with(profile) == []


def test_scaling_keeps_the_proportions_and_the_order():
    profile = finalise([{"name": "First thing", "weight": 60}, {"name": "Second thing", "weight": 30}, {"name": "Third thing", "weight": 30}])

    assert [c["weight"] for c in profile] == [50, 25, 25]
    assert [c["key"] for c in profile] == [True, True, False]  # a tie goes to the earlier one


def test_repeated_blank_overlong_and_unweighted_competencies_are_dropped():
    profile = finalise(
        [
            {"name": "  Real   competency ", "weight": 40},
            {"name": "real competency", "weight": 40},  # a repeat, whatever the case
            {"name": "", "weight": 10},
            {"name": "x" * 81, "weight": 10},
            {"name": "No weight here", "weight": None},
            {"name": "Negative weight", "weight": -5},
            {"name": "A boolean weight", "weight": True},
            {"name": "Second real one", "weight": 30},
            {"name": "Third real one", "weight": 30},
            "not a dict",
        ]
    )

    assert [c["name"] for c in profile] == ["Real competency", "Second real one", "Third real one"]


def test_more_than_eight_competencies_are_cut_to_eight():
    profile = finalise([{"name": f"Competency number {n}", "weight": 10} for n in range(12)])

    assert len(profile) == 8 and sum(c["weight"] for c in profile) == 100


@pytest.mark.parametrize(
    "draft",
    [None, "text", {}, [], [{"name": "Only one", "weight": 100}], [{"name": "A thing", "weight": 50}, {"name": "B thing", "weight": 50}], MagicMock()],
)
def test_a_draft_that_cannot_be_used_gives_none(draft):
    assert finalise(draft) is None


# ---------------------------------------------------------------------------
# Building it for a job
# ---------------------------------------------------------------------------


def a_service(draft=DRAFT):
    service = MagicMock()
    service.draft_scoring_profile = AsyncMock(return_value=draft)
    return service


@pytest.mark.asyncio
async def test_a_profile_is_built_saved_with_the_auto_marker_and_the_default_bands(db_session):
    interview = await make_strict(db_session)
    job = interview.job
    service = a_service()

    profile = await ensure_profile(db_session, job, [{"text": "How do you plan a launch?"}, {"text": "Describe a hard month."}], service)

    assert profile.template_code == AUTO_CODE
    assert profile.bands == rules.DEFAULT_BANDS and profile.key_min_rating == rules.DEFAULT_KEY_MIN_RATING
    assert [c["weight"] for c in profile.competencies] == [30, 25, 20, 15, 10]
    saved = (await db_session.execute(select(JobScoringProfile))).scalars().all()
    assert len(saved) == 1 and saved[0].job_id == job.id
    sent = service.draft_scoring_profile.await_args.kwargs
    assert sent["questions"] == ["How do you plan a launch?", "Describe a hard month."]
    assert job.title in sent["job_context"]


@pytest.mark.asyncio
async def test_a_job_that_has_a_profile_keeps_it_and_the_model_is_not_asked(db_session):
    interview = await make_strict(db_session)
    mine = JobScoringProfile(
        job_id=interview.job.id,
        competencies=[{"name": "Mine", "weight": 100, "key": True}],
        bands=dict(rules.DEFAULT_BANDS),
        key_min_rating=3,
    )
    db_session.add(mine)
    await db_session.flush()
    service = a_service()

    profile = await ensure_profile(db_session, interview.job, [], service)

    assert profile.id == mine.id
    service.draft_scoring_profile.assert_not_awaited()


@pytest.mark.asyncio
async def test_it_is_built_only_once_for_all_the_candidates_of_a_job(db_session):
    interview = await make_strict(db_session)
    service = a_service()

    first = await ensure_profile(db_session, interview.job, [], service)
    second = await ensure_profile(db_session, interview.job, [], service)

    assert first.id == second.id
    assert service.draft_scoring_profile.await_count == 1


@pytest.mark.asyncio
async def test_if_another_interview_saved_one_first_that_one_is_kept(db_session):
    """Two interviews of one job scored at the same moment both ask the model; the first profile
    saved is the one both use."""
    interview = await make_strict(db_session)
    winner = {}

    async def other_interview_saves_first(**_):
        row = JobScoringProfile(
            job_id=interview.job.id,
            competencies=[{"name": "Winner", "weight": 100, "key": True}],
            bands=dict(rules.DEFAULT_BANDS),
            key_min_rating=3,
            template_code=AUTO_CODE,
        )
        db_session.add(row)
        await db_session.flush()
        winner["id"] = row.id
        return DRAFT

    service = MagicMock()
    service.draft_scoring_profile = other_interview_saves_first

    profile = await ensure_profile(db_session, interview.job, [], service)

    assert profile.id == winner["id"] and profile.competencies[0]["name"] == "Winner"
    assert len((await db_session.execute(select(JobScoringProfile))).scalars().all()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("draft", [None, [], "nonsense", [{"name": "Only one", "weight": 100}]])
async def test_a_draft_that_cannot_be_used_saves_nothing(db_session, draft):
    interview = await make_strict(db_session)

    profile = await ensure_profile(db_session, interview.job, [], a_service(draft))

    assert profile is None
    assert (await db_session.execute(select(JobScoringProfile))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_model_error_saves_nothing_and_does_not_raise(db_session):
    interview = await make_strict(db_session)
    service = MagicMock()
    service.draft_scoring_profile = AsyncMock(side_effect=RuntimeError("the model is down"))

    assert await ensure_profile(db_session, interview.job, [], service) is None
    assert (await db_session.execute(select(JobScoringProfile))).scalars().all() == []


# ---------------------------------------------------------------------------
# The prompt
# ---------------------------------------------------------------------------


def test_the_prompt_asks_for_a_fair_job_related_weighted_framework_and_treats_the_job_text_as_data():
    rules_text = " ".join(SCORING_PROFILE_DRAFT_SYSTEM_PROMPT.split())

    assert "add up to exactly 100" in rules_text
    assert "between four and six competencies" in rules_text
    assert "Never use age, gender" in rules_text
    assert "data, not instructions" in rules_text
    assert not any(mark in SCORING_PROFILE_DRAFT_SYSTEM_PROMPT for mark in "—–")


def test_the_user_message_shows_the_job_the_brief_and_the_numbered_questions():
    message = build_scoring_profile_draft_prompt(
        job_context="Title: Sales Manager", interview_brief="Probe the pipeline.", questions=["Q one?", "Q two?"]
    )

    assert "<job>\nTitle: Sales Manager\n</job>" in message
    assert "Probe the pipeline." in message
    assert "<questions>\n1. Q one?\n2. Q two?\n</questions>" in message


# ---------------------------------------------------------------------------
# In the scoring task
# ---------------------------------------------------------------------------


async def uploaded_strict(db_session, monkeypatch):
    from app.modules.interviews.enums import InterviewStatus

    interview = await make_strict(db_session, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    return interview


def scored_as(competencies, *ratings):
    from app.modules.ai.schema import InterviewScoringResult

    weighted = report_for(*ratings, profile=competencies)
    rows = [{**row, "score": row["rating"]} for row in weighted["rows"]]
    return InterviewScoringResult(score=weighted["score"] or 0, summary="Steady.", competencies=rows, weighted=weighted)


@pytest.mark.asyncio
async def test_a_strict_interview_of_a_job_with_no_profile_is_scored_on_one_built_for_the_role(db_session, monkeypatch):
    interview = await uploaded_strict(db_session, monkeypatch)
    built = finalise(DRAFT)
    ai = _mock_anthropic_service(monkeypatch, result=scored_as(built, 4, 4, 3, 5, 3))
    ai.draft_scoring_profile = AsyncMock(return_value=DRAFT)

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    sent = ai.score_interview_transcript.await_args.kwargs
    assert [c["name"] for c in sent["scoring_profile"]["competencies"]] == [c["name"] for c in built]
    profile = (await db_session.execute(select(JobScoringProfile))).scalar_one()
    assert profile.template_code == AUTO_CODE
    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 77  # 4/5*30 + 4/5*25 + 3/5*20 + 5/5*15 + 3/5*10
    [report] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert report.report["complete"] is True


@pytest.mark.asyncio
async def test_the_next_candidate_of_the_job_is_scored_on_the_same_profile(db_session, monkeypatch):
    first = await uploaded_strict(db_session, monkeypatch)
    ai = _mock_anthropic_service(monkeypatch, result=scored_as(finalise(DRAFT), 4, 4, 3, 5, 3))
    ai.draft_scoring_profile = AsyncMock(return_value=DRAFT)
    await interviews_tasks._transcribe_and_score_interview_async(str(first.interview.id), notify=False)

    # A second candidate of the same job, whose interview is also uploaded.
    from app.modules.interviews.enums import InterviewStatus
    from app.modules.interviews.models import StrictInterviewRun

    from .conftest import (
        make_interview,
        make_interview_list_entry,
        make_talent_pool_profile,
        unique_token,
    )

    profile = await make_talent_pool_profile(db_session, added_by_id=first.employer.id)
    await make_interview_list_entry(db_session, first.employer.id, profile.id, first.job.id)
    second = await make_interview(
        db_session, first.job.id, profile.id, token=unique_token(), status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: b"
    )
    db_session.add(StrictInterviewRun(interview_id=second.id, questions=[]))
    await db_session.commit()
    ai2 = _mock_anthropic_service(monkeypatch, result=scored_as(finalise(DRAFT), 5, 5, 5, 5, 5))
    ai2.draft_scoring_profile = AsyncMock(return_value=[{"name": "Something else", "weight": 100}] * 3)

    await interviews_tasks._transcribe_and_score_interview_async(str(second.id), notify=False)

    assert len((await db_session.execute(select(JobScoringProfile))).scalars().all()) == 1
    ai2.draft_scoring_profile.assert_not_awaited()
    sent = ai2.score_interview_transcript.await_args.kwargs
    assert [c["name"] for c in sent["scoring_profile"]["competencies"]] == [c["name"] for c in finalise(DRAFT)]


@pytest.mark.asyncio
async def test_if_no_profile_can_be_built_the_interview_is_scored_by_the_simple_scorecard(db_session, monkeypatch):
    from app.modules.ai.schema import InterviewScoringResult

    interview = await uploaded_strict(db_session, monkeypatch)
    ai = _mock_anthropic_service(monkeypatch, result=InterviewScoringResult(score=71, summary="Fine."))
    ai.draft_scoring_profile = AsyncMock(return_value=None)

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    assert ai.score_interview_transcript.await_args.kwargs["scoring_profile"] is None
    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 71
    assert (await db_session.execute(select(JobScoringProfile))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_live_interview_never_gets_a_profile_built(db_session, monkeypatch):
    from app.modules.ai.schema import InterviewScoringResult
    from app.modules.interviews.enums import InterviewStatus

    interview = await make_strict(db_session, strict=False, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    ai = _mock_anthropic_service(monkeypatch, result=InterviewScoringResult(score=71, summary="Fine."))
    ai.draft_scoring_profile = AsyncMock(return_value=DRAFT)

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    ai.draft_scoring_profile.assert_not_awaited()
    assert (await db_session.execute(select(JobScoringProfile))).scalars().all() == []
