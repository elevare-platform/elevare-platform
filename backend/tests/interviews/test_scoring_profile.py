"""Scoring profiles: competencies with weights, the weighted score, the bands, and how a strict
interview is scored with one (docs/08_DECISIONS.md, item 36; docs/16_COLTON_BRIEF.md sections 3
and 4)."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.modules.ai.prompts.interview_scoring import describe_scoring_profile
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews import scoring_profile as rules
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.assessment_text import format_assessment
from app.modules.interviews.models import InterviewWeightedScore, JobInterviewQuestion
from app.modules.interviews.scoring_profile import (
    BAND_HOLD,
    BAND_NOT,
    BAND_SHORTLIST,
    BAND_STRONG,
    normalise,
    problems_with,
    tidy,
    weighted_report,
)
from tests.conftest import make_employer, make_job

from .test_interview_tasks import (
    _mock_anthropic_service,
    _patch_engine_to_use_test_session,
)
from .test_strict_interview import make_strict

COMPETENCIES = [
    {"name": "Strategy", "weight": 25, "key": True},
    {"name": "P&L", "weight": 20, "key": True},
    {"name": "Route to market", "weight": 20, "key": False},
    {"name": "Leadership", "weight": 15, "key": False},
    {"name": "Brand", "weight": 10, "key": False},
    {"name": "Execution", "weight": 10, "key": False},
]


def rated(*ratings, profile=COMPETENCIES):
    """The model's ratings for the profile, in its order (None for not assessed)."""
    return [
        {"name": item["name"], "score": rating, "coverage": "FULLY_ASSESSED" if rating else "NOT_ASSESSED"}
        for item, rating in zip(profile, ratings, strict=True)
    ]


def report_for(*ratings, bands=None, key_min=3, profile=COMPETENCIES):
    return weighted_report(normalise(rated(*ratings, profile=profile), profile), bands, key_min)


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("template", rules.TEMPLATES, ids=lambda t: t["code"])
def test_each_template_adds_up_to_100_with_the_two_heaviest_competencies_as_key(template):
    competencies = template["competencies"]

    assert sum(item["weight"] for item in competencies) == 100
    assert problems_with(competencies) == []
    names = [item["name"] for item in competencies]
    assert len({name.casefold() for name in names}) == len(names)
    heaviest_two = sorted(competencies, key=lambda item: -item["weight"])[:2]
    assert [item["name"] for item in competencies if item["key"]] == [item["name"] for item in heaviest_two]


def test_the_templates_are_the_clients_three_roles_with_their_weights():
    by_code = {template["code"]: [item["weight"] for item in template["competencies"]] for template in rules.TEMPLATES}

    assert by_code == {
        "commercial_director": [25, 20, 20, 15, 10, 10],
        "national_sales_manager": [30, 25, 15, 15, 10, 5],
        "senior_marketing_manager": [25, 20, 20, 15, 10, 10],
    }


def test_a_valid_profile_has_no_problems():
    assert problems_with(COMPETENCIES, rules.DEFAULT_BANDS, 3) == []


@pytest.mark.parametrize(
    ("competencies", "fragment"),
    [
        ([{"name": "A", "weight": 60}, {"name": "B", "weight": 30}], "add up to 90%, and must add up to 100%"),
        ([{"name": "A", "weight": 60}, {"name": "B", "weight": 50}], "add up to 110%"),
        ([{"name": "A", "weight": 100}], "between 2 and 12"),
        ([{"name": f"C{n}", "weight": 1} for n in range(13)], "between 2 and 12"),
        ([{"name": "A", "weight": 50}, {"name": "a ", "weight": 50}], "\"a\" is listed twice"),
        ([{"name": "  ", "weight": 50}, {"name": "B", "weight": 50}], "Competency 1 needs a name"),
        ([{"name": "A", "weight": 0}, {"name": "B", "weight": 100}], "whole-number weight from 1 to 100"),
        ([{"name": "A", "weight": 50.5}, {"name": "B", "weight": 49.5}], "whole-number weight"),
        ([{"name": "A", "weight": True}, {"name": "B", "weight": 99}], "whole-number weight"),
        ([{"name": "A" * 81, "weight": 50}, {"name": "B", "weight": 50}], "name over 80 characters"),
    ],
)
def test_a_profile_that_breaks_a_rule_is_refused_with_the_problem_named(competencies, fragment):
    assert any(fragment in problem for problem in problems_with(competencies)), problems_with(competencies)


@pytest.mark.parametrize(
    ("bands", "key_min", "fragment"),
    [
        ({"strong": 70, "shortlist": 75, "hold": 65}, 3, "must go down"),
        ({"strong": 85, "shortlist": 85, "hold": 65}, 3, "must go down"),
        ({"strong": 101, "shortlist": 75, "hold": 65}, 3, "whole numbers from 1 to 100"),
        ({"strong": 85, "shortlist": 75, "hold": 0}, 3, "whole numbers from 1 to 100"),
        (rules.DEFAULT_BANDS, 0, "from 1 to 5"),
        (rules.DEFAULT_BANDS, 6, "from 1 to 5"),
    ],
)
def test_bands_and_the_key_minimum_are_checked(bands, key_min, fragment):
    assert any(fragment in problem for problem in problems_with(COMPETENCIES, bands, key_min))


def test_what_is_stored_has_tidy_names_whole_weights_and_a_key_flag_on_each():
    stored = tidy([{"name": "  Brand   strategy ", "weight": 25}, {"name": "P&L", "weight": 75, "key": True}])

    assert stored == [
        {"name": "Brand strategy", "weight": 25, "key": False},
        {"name": "P&L", "weight": 75, "key": True},
    ]


# --- lining the model's ratings up with the profile ----------------------------------------


def test_the_rows_follow_the_profile_in_its_order_and_its_spelling():
    rows = normalise(
        [{"name": "p&l", "score": 4}, {"name": "STRATEGY", "score": 5, "coverage": "FULLY_ASSESSED"}], COMPETENCIES
    )

    assert [row["name"] for row in rows] == [item["name"] for item in COMPETENCIES]
    assert [row["rating"] for row in rows][:2] == [5, 4]
    assert [row["weight"] for row in rows] == [25, 20, 20, 15, 10, 10]
    assert [row["key"] for row in rows][:3] == [True, True, False]


def test_a_competency_the_model_did_not_rate_is_not_assessed_never_a_zero():
    rows = normalise([{"name": "Strategy", "score": 4}], COMPETENCIES)

    assert rows[1]["rating"] is None and rows[1]["coverage"] == "NOT_ASSESSED"


def test_a_rating_for_a_name_the_profile_does_not_have_is_dropped():
    rows = normalise([{"name": "Charisma", "score": 5}], COMPETENCIES)

    assert len(rows) == 6 and all(row["rating"] is None for row in rows)


@pytest.mark.parametrize("bad", [0, 6, -1, 3.5, "4", True, None])
def test_a_rating_that_is_not_a_whole_number_from_1_to_5_is_not_assessed(bad):
    [row] = normalise([{"name": "A", "score": bad}], [{"name": "A", "weight": 100, "key": False}])

    assert row["rating"] is None and row["coverage"] == "NOT_ASSESSED"


# --- the weighted score ------------------------------------------------------------------------


def test_the_total_is_the_sum_of_rating_over_five_times_the_weight():
    report = report_for(4, 3, 5, 4, 5, 3)  # 20 + 12 + 20 + 12 + 10 + 6

    assert report["points"] == 80 and report["score"] == 80
    assert report["complete"] is True and report["assessed_weight"] == 100 and report["total_weight"] == 100


def test_all_fives_is_100_and_all_ones_is_20():
    assert report_for(5, 5, 5, 5, 5, 5)["score"] == 100
    assert report_for(1, 1, 1, 1, 1, 1)["score"] == 20


def test_the_total_is_rounded_to_a_whole_number():
    report = report_for(4, 4, 4, 4, 4, 3)  # 20 + 16 + 16 + 12 + 8 + 6 = 78
    other = report_for(3, 3, 3, 3, 3, 4)  # 15 + 12 + 12 + 9 + 6 + 8 = 62

    assert report["score"] == 78 and other["score"] == 62
    half = weighted_report(
        normalise([{"name": "A", "score": 3}, {"name": "B", "score": 4}], [{"name": "A", "weight": 33}, {"name": "B", "weight": 67}]),
        None,
        3,
    )  # 19.8 + 53.6 = 73.4
    assert half["points"] == 73.4 and half["score"] == 73


def test_a_competency_not_assessed_makes_the_score_incomplete_with_no_number_and_no_band():
    report = report_for(4, None, 5, 4, 5, 3)  # P&L (20) was not assessed

    assert report["complete"] is False
    assert report["score"] is None and report["band"] is None
    assert report["points"] == 68  # 20 + 20 + 12 + 10 + 6, and nothing for P&L (not a zero)
    assert report["assessed_weight"] == 80 and report["unassessed"] == ["P&L"]


def test_nothing_assessed_is_incomplete_with_zero_points_not_a_failing_score():
    report = weighted_report(normalise([], COMPETENCIES), None, 3)

    assert report["complete"] is False and report["points"] == 0
    assert report["assessed_weight"] == 0 and report["score"] is None and report["band"] is None


# --- the bands ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100, BAND_STRONG), (85, BAND_STRONG), (84, BAND_SHORTLIST), (75, BAND_SHORTLIST),
        (74, BAND_HOLD), (65, BAND_HOLD), (64, BAND_NOT), (20, BAND_NOT),
    ],
)
def test_the_bands_use_the_clients_thresholds_at_and_around_each_boundary(score, band):
    assert rules.band_for(score, rules.DEFAULT_BANDS) == band


def test_the_thresholds_can_be_changed_for_a_job():
    custom = {"strong": 90, "shortlist": 80, "hold": 70}

    assert rules.band_for(85, custom) == BAND_SHORTLIST
    assert rules.band_for(85, rules.DEFAULT_BANDS) == BAND_STRONG


def test_a_key_competency_under_the_minimum_holds_a_strong_or_shortlist_band_at_hold():
    strong = report_for(2, 5, 5, 5, 5, 5)  # 10 + 20 + 20 + 15 + 10 + 10 = 85, but Strategy (key) is a 2
    other = report_for(5, 2, 5, 5, 5, 4)  # 25 + 8 + 20 + 15 + 10 + 8 = 86, but P&L (key) is a 2

    assert strong["score"] == 85 and strong["key_flags"] == ["Strategy"] and strong["band"] == BAND_HOLD
    assert other["score"] == 86 and other["key_flags"] == ["P&L"] and other["band"] == BAND_HOLD


def test_the_key_gate_never_makes_a_weak_band_worse_or_turns_into_do_not_shortlist_by_itself():
    hold = report_for(2, 3, 3, 3, 3, 3)  # a key competency under 3 on a total that is already Hold or lower
    high = report_for(2, 5, 5, 5, 5, 5)

    assert rules.band_for(70, rules.DEFAULT_BANDS, capped=True) == BAND_HOLD
    assert rules.band_for(60, rules.DEFAULT_BANDS, capped=True) == BAND_NOT  # the total alone says so
    assert high["band"] != BAND_NOT
    assert hold["key_flags"] == ["Strategy"]


def test_a_key_competency_at_the_minimum_is_not_flagged_and_a_non_key_one_never_is():
    clean = report_for(3, 3, 1, 1, 1, 1)  # key ones at 3; the weak ones are not key

    assert clean["key_flags"] == []


def test_the_minimum_for_a_key_competency_can_be_changed():
    strict = report_for(3, 5, 5, 5, 5, 5, key_min=4)

    assert strict["key_flags"] == ["Strategy"]


def test_a_key_competency_that_was_not_assessed_is_not_flagged_it_makes_the_score_incomplete():
    report = report_for(None, 5, 5, 5, 5, 5)

    assert report["key_flags"] == [] and report["complete"] is False and report["unassessed"] == ["Strategy"]


# ---------------------------------------------------------------------------
# What the model is told, and how its reply is used
# ---------------------------------------------------------------------------


def test_the_prompt_lists_the_competencies_with_weights_and_key_marks_and_the_question_tags():
    text = describe_scoring_profile(
        COMPETENCIES,
        [
            {"number": 1, "text": "How would you set strategy?", "competency": "Strategy"},
            {"number": 2, "text": "Tell me about yourself.", "competency": None},
        ],
    )

    assert "- Strategy (weight 25%) [key]" in text and "- Brand (weight 10%)" in text
    assert "Rate EXACTLY these" in text and "never give it a 1 for lack of evidence" in text
    assert 'Question 1: "How would you set strategy?" tests: Strategy' in text
    assert "Question 2" not in text  # an untagged question is not listed
    assert "do not work out the overall score" in text


def test_without_a_profile_the_prompt_says_to_choose_the_competencies_as_before():
    assert "Not set. Choose the competencies from the interview brief" in describe_scoring_profile(None)


def _service_returning(payload):
    service = AnthropicCVExtractionService.__new__(AnthropicCVExtractionService)
    response = MagicMock()
    response.content = [MagicMock(text=json.dumps(payload))]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=2000, output_tokens=900)
    service._client = AsyncMock()
    service._client.messages.create = AsyncMock(return_value=response)
    return service


PROFILE = {"competencies": COMPETENCIES, "bands": dict(rules.DEFAULT_BANDS), "key_min_rating": 3}


async def score(service, **kwargs):
    return await service.score_interview_transcript(
        interview_brief="Brief.", transcript="AI: q\n\nCandidate: a", scoring_profile=PROFILE, **kwargs
    )


@pytest.mark.asyncio
async def test_the_weighted_total_comes_from_the_ratings_and_the_models_own_number_is_ignored():
    service = _service_returning(
        {"score": 99, "summary": "Good.", "competencies": rated(4, 3, 5, 4, 5, 3)}
    )

    result = await score(service)

    assert result.failed is False
    assert result.weighted["score"] == 80 and result.weighted["complete"] is True
    assert result.weighted["band"] == BAND_SHORTLIST


@pytest.mark.asyncio
async def test_a_reply_with_no_overall_score_is_fine_when_the_ratings_are_there():
    result = await score(_service_returning({"summary": "Good.", "competencies": rated(3, 3, 3, 3, 3, 3)}))

    assert result.failed is False and result.weighted["score"] == 60


@pytest.mark.asyncio
async def test_a_competency_missing_from_the_reply_is_not_assessed_and_the_score_incomplete():
    result = await score(_service_returning({"summary": "Partial.", "competencies": rated(4, 3, None, 4, 5, 3)}))

    assert result.weighted["complete"] is False and result.weighted["unassessed"] == ["Route to market"]
    assert result.weighted["score"] is None


@pytest.mark.asyncio
async def test_a_reply_without_a_list_of_ratings_is_a_failure_when_a_profile_is_set():
    result = await score(_service_returning({"score": 80, "summary": "No ratings."}))

    assert result.failed is True


@pytest.mark.asyncio
async def test_the_profile_and_the_question_tags_reach_the_model():
    service = _service_returning({"summary": "x", "competencies": rated(3, 3, 3, 3, 3, 3)})

    await score(service, question_tags=[{"number": 1, "text": "How do you plan?", "competency": "Strategy"}])

    sent = service._client.messages.create.await_args.kwargs["messages"][0]["content"]
    assert "- P&L (weight 20%) [key]" in sent
    assert 'Question 1: "How do you plan?" tests: Strategy' in sent


@pytest.mark.asyncio
async def test_without_a_profile_scoring_is_the_generic_scorecard_as_before():
    service = _service_returning({"score": 64, "summary": "Fine."})

    result = await service.score_interview_transcript(interview_brief="B.", transcript="AI: q\n\nCandidate: a")

    assert result.failed is False and result.score == 64 and result.weighted is None


# --- the assessment text ---------------------------------------------------------------------


def result_with(weighted, **over):
    from app.modules.ai.schema import InterviewScoringResult

    rows = [{**row, "score": row["rating"]} for row in weighted["rows"]]
    return InterviewScoringResult(
        score=weighted["score"] or 0, summary="A steady candidate.", competencies=rows, weighted=weighted,
        recommendation="Recommend", **over,
    )


def test_a_complete_score_says_the_total_the_provisional_band_and_drops_the_four_word_recommendation():
    text = format_assessment(result_with(report_for(4, 3, 5, 4, 5, 3)))

    assert "Weighted score: 80 of 100. Suggested band (provisional): Shortlist." in text
    assert "Overall recommendation" not in text
    assert "- Strategy (weight 25%, key): 4 of 5" in text


def test_an_incomplete_score_says_so_with_what_was_assessed_and_gives_no_band():
    text = format_assessment(result_with(report_for(4, None, 5, 4, 5, 3)))

    assert "INCOMPLETE SCORE: 68 of 80 weighted points could be assessed (not assessed: P&L)." in text
    assert "No full score and no band are given." in text
    assert "Suggested band" not in text and "Weighted score:" not in text


def test_a_key_competency_under_the_minimum_is_named_with_the_hold():
    text = format_assessment(result_with(report_for(2, 5, 5, 5, 5, 5)))

    assert "Key competency rated under 3 of 5: Strategy." in text
    assert "held at Hold for evidence" in text and "Suggested band (provisional): Hold for evidence" in text


# ---------------------------------------------------------------------------
# Saving a profile, over HTTP
# ---------------------------------------------------------------------------


def headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


async def a_job(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Find out about strategy.")
    db_session.add(job)
    await db_session.flush()
    return employer, job


def url(job, tail="scoring-profile"):
    return f"/api/v1/interviews/jobs/{job.id}/{tail}"


BODY = {"competencies": COMPETENCIES}


@pytest.mark.asyncio
async def test_a_job_has_no_profile_until_one_is_saved_and_the_editor_gets_the_templates(client, db_session):
    employer, job = await a_job(db_session)

    body = (await client.get(url(job), headers=headers(employer))).json()

    assert body["profile"] is None
    assert [t["code"] for t in body["templates"]] == ["commercial_director", "national_sales_manager", "senior_marketing_manager"]
    assert body["default_bands"] == rules.DEFAULT_BANDS and body["default_key_min_rating"] == 3


@pytest.mark.asyncio
async def test_a_valid_profile_is_saved_with_the_default_bands_and_read_back(client, db_session):
    employer, job = await a_job(db_session)

    saved = await client.put(url(job), json={**BODY, "template_code": "commercial_director"}, headers=headers(employer))
    again = (await client.get(url(job), headers=headers(employer))).json()

    assert saved.status_code == 200
    assert again["profile"]["competencies"] == COMPETENCIES
    assert again["profile"]["bands"] == rules.DEFAULT_BANDS and again["profile"]["key_min_rating"] == 3
    assert again["profile"]["template_code"] == "commercial_director"


@pytest.mark.asyncio
async def test_saving_again_replaces_it_and_never_makes_a_second(client, db_session):
    from app.modules.interviews.models import JobScoringProfile

    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))
    other = {"competencies": [{"name": "Only", "weight": 60, "key": True}, {"name": "Two", "weight": 40, "key": False}],
             "bands": {"strong": 90, "shortlist": 80, "hold": 70}, "key_min_rating": 4}

    await client.put(url(job), json=other, headers=headers(employer))

    rows = (await db_session.execute(select(JobScoringProfile).where(JobScoringProfile.job_id == job.id))).scalars().all()
    assert len(rows) == 1 and rows[0].bands == {"strong": 90, "shortlist": 80, "hold": 70}
    assert [c["name"] for c in rows[0].competencies] == ["Only", "Two"] and rows[0].key_min_rating == 4


@pytest.mark.asyncio
async def test_a_profile_that_breaks_a_rule_is_refused_with_every_problem_and_nothing_is_saved(client, db_session):
    employer, job = await a_job(db_session)
    bad = {"competencies": [{"name": "A", "weight": 50}, {"name": "a", "weight": 30}],
           "bands": {"strong": 60, "shortlist": 70, "hold": 80}}

    resp = await client.put(url(job), json=bad, headers=headers(employer))

    assert resp.status_code == 422
    message = resp.json()["message"]
    assert "listed twice" in message and "add up to 80%" in message and "must go down" in message
    assert (await client.get(url(job), headers=headers(employer))).json()["profile"] is None


@pytest.mark.asyncio
async def test_another_company_cannot_read_save_or_remove_a_profile(client, db_session):
    _owner, job = await a_job(db_session)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.flush()

    assert (await client.get(url(job), headers=headers(stranger))).status_code == 403
    assert (await client.put(url(job), json=BODY, headers=headers(stranger))).status_code == 403
    assert (await client.delete(url(job), headers=headers(stranger))).status_code == 403
    assert (await client.get(url(job))).status_code == 401


@pytest.mark.asyncio
async def test_removing_the_profile_sends_the_job_back_to_the_generic_scorecard(client, db_session):
    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))

    resp = await client.delete(url(job), headers=headers(employer))

    assert resp.status_code == 200 and resp.json()["profile"] is None
    assert (await client.get(url(job), headers=headers(employer))).json()["profile"] is None
    assert (await client.delete(url(job), headers=headers(employer))).status_code == 200  # again: nothing to remove


# --- the competency tag on a question ---------------------------------------------------------


def question(text, competency=None, seconds=120):
    return {"text": text, "time_limit_seconds": seconds, "source": "EMPLOYER", "competency": competency}


@pytest.mark.asyncio
async def test_a_question_can_be_tagged_with_a_competency_spelled_as_the_profile_spells_it(client, db_session):
    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))

    resp = await client.put(
        url(job, "questions"),
        json={"questions": [question("How do you set a strategy for launches?", "strategy"), question("Tell me about a time you led a team.")]},
        headers=headers(employer),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [q["competency"] for q in body["questions"]] == ["Strategy", None]
    assert body["competencies"] == [c["name"] for c in COMPETENCIES]
    assert body["untested_competencies"] == [c["name"] for c in COMPETENCIES if c["name"] != "Strategy"]


@pytest.mark.asyncio
async def test_a_tag_that_is_not_a_competency_of_the_profile_is_refused_naming_the_question(client, db_session):
    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))

    resp = await client.put(
        url(job, "questions"),
        json={"questions": [question("How do you set a strategy for launches?"), question("Tell me about a time you led.", "Charisma")]},
        headers=headers(employer),
    )

    assert resp.status_code == 422
    assert 'Question 2 is tagged "Charisma", which is not a competency of this job\'s scoring profile.' in resp.json()["message"]


@pytest.mark.asyncio
async def test_a_tag_needs_a_profile_to_point_to(client, db_session):
    employer, job = await a_job(db_session)

    resp = await client.put(
        url(job, "questions"),
        json={"questions": [question("How do you set a strategy for launches?", "Strategy")]},
        headers=headers(employer),
    )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_questions_without_tags_save_as_before_and_the_list_names_the_untested_competencies(client, db_session):
    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))

    body = (
        await client.put(
            url(job, "questions"),
            json={"questions": [question("How do you set a strategy for launches?")]},
            headers=headers(employer),
        )
    ).json()

    assert body["questions"][0]["competency"] is None
    assert body["untested_competencies"] == [c["name"] for c in COMPETENCIES]


@pytest.mark.asyncio
async def test_changing_the_profile_clears_the_tags_that_no_longer_point_anywhere(client, db_session):
    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))
    await client.put(
        url(job, "questions"),
        json={"questions": [question("How do you set a strategy for launches?", "Strategy"), question("How do you manage the P and L?", "P&L")]},
        headers=headers(employer),
    )
    renamed = [{**c, "name": "Commercial strategy"} if c["name"] == "Strategy" else c for c in COMPETENCIES]

    await client.put(url(job), json={"competencies": renamed}, headers=headers(employer))

    body = (await client.get(url(job, "questions"), headers=headers(employer))).json()
    assert [q["competency"] for q in body["questions"]] == [None, "P&L"]


@pytest.mark.asyncio
async def test_removing_the_profile_clears_every_tag(client, db_session):
    employer, job = await a_job(db_session)
    await client.put(url(job), json=BODY, headers=headers(employer))
    await client.put(url(job, "questions"), json={"questions": [question("How do you set a strategy for launches?", "Strategy")]}, headers=headers(employer))

    await client.delete(url(job), headers=headers(employer))

    rows = (await db_session.execute(select(JobInterviewQuestion).where(JobInterviewQuestion.job_id == job.id))).scalars().all()
    assert [row.competency for row in rows] == [None]


# ---------------------------------------------------------------------------
# Scoring a strict interview that has a profile
# ---------------------------------------------------------------------------


async def strict_with_profile(db_session, monkeypatch, tags=("Strategy", None)):
    from app.modules.interviews.enums import InterviewStatus
    from app.modules.interviews.models import JobScoringProfile, StrictInterviewRun

    interview = await make_strict(db_session, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    db_session.add(JobScoringProfile(job_id=interview.job.id, competencies=COMPETENCIES, bands=dict(rules.DEFAULT_BANDS), key_min_rating=3))
    run = (await db_session.execute(select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview.interview.id))).scalar_one()
    run.questions = [
        {"text": "How do you set a strategy?", "time_limit_seconds": 120, "competency": tags[0]},
        {"text": "Tell me about yourself.", "time_limit_seconds": 120, "competency": tags[1]},
    ]
    await db_session.commit()
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    return interview


def scoring_result(*ratings):
    from app.modules.ai.schema import InterviewScoringResult

    weighted = report_for(*ratings)
    rows = [{**row, "score": row["rating"]} for row in weighted["rows"]]
    return InterviewScoringResult(score=weighted["score"] or 0, summary="A steady candidate.", competencies=rows, weighted=weighted)


@pytest.mark.asyncio
async def test_a_complete_weighted_score_is_stored_as_the_interviews_score_with_its_report(db_session, monkeypatch):
    interview = await strict_with_profile(db_session, monkeypatch)
    ai = _mock_anthropic_service(monkeypatch, result=scoring_result(4, 3, 5, 4, 5, 3))

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 80
    assert "Weighted score: 80 of 100. Suggested band (provisional): Shortlist." in interview.interview.ai_rationale
    [report] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert report.interview_id == interview.interview.id
    assert report.report["score"] == 80 and report.report["band"] == BAND_SHORTLIST
    sent = ai.score_interview_transcript.await_args.kwargs
    assert [c["name"] for c in sent["scoring_profile"]["competencies"]] == [c["name"] for c in COMPETENCIES]
    assert sent["question_tags"] == [
        {"number": 1, "text": "How do you set a strategy?", "competency": "Strategy"},
        {"number": 2, "text": "Tell me about yourself.", "competency": None},
    ]


@pytest.mark.asyncio
async def test_an_incomplete_score_is_never_stored_as_a_number_but_the_report_and_the_text_are(db_session, monkeypatch):
    interview = await strict_with_profile(db_session, monkeypatch)
    _mock_anthropic_service(monkeypatch, result=scoring_result(4, None, 5, 4, 5, 3))

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score is None
    assert interview.interview.status == "SCORED"
    assert "INCOMPLETE SCORE" in interview.interview.ai_rationale
    [report] = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert report.report["complete"] is False and report.report["score"] is None


@pytest.mark.asyncio
async def test_scoring_again_replaces_the_report_instead_of_adding_a_second(db_session, monkeypatch):
    interview = await strict_with_profile(db_session, monkeypatch)
    _mock_anthropic_service(monkeypatch, result=scoring_result(4, None, 5, 4, 5, 3))
    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)
    await db_session.refresh(interview.interview)
    interview.interview.status = "UPLOADED"
    await db_session.commit()
    _mock_anthropic_service(monkeypatch, result=scoring_result(5, 5, 5, 5, 5, 5))

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    rows = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert len(rows) == 1 and rows[0].report["score"] == 100
    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 100


@pytest.mark.asyncio
async def test_a_job_without_a_profile_is_scored_by_the_generic_scorecard(db_session, monkeypatch):
    from app.modules.ai.schema import InterviewScoringResult
    from app.modules.interviews.enums import InterviewStatus

    interview = await make_strict(db_session, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    ai = _mock_anthropic_service(monkeypatch, result=InterviewScoringResult(score=71, summary="Fine."))

    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)

    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 71
    assert ai.score_interview_transcript.await_args.kwargs["scoring_profile"] is None
    assert (await db_session.execute(select(InterviewWeightedScore))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_live_interview_is_never_scored_with_a_profile(db_session, monkeypatch):
    from app.modules.ai.schema import InterviewScoringResult
    from app.modules.interviews.enums import InterviewStatus
    from app.modules.interviews.models import JobScoringProfile

    live = await make_strict(db_session, strict=False, status=InterviewStatus.UPLOADED.value, transcript="AI: q\n\nCandidate: a")
    db_session.add(JobScoringProfile(job_id=live.job.id, competencies=COMPETENCIES, bands=dict(rules.DEFAULT_BANDS), key_min_rating=3))
    await db_session.commit()
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    monkeypatch.setattr(interviews_tasks, "assert_can_score_interviews", AsyncMock())
    ai = _mock_anthropic_service(monkeypatch, result=InterviewScoringResult(score=66, summary="Fine."))

    await interviews_tasks._transcribe_and_score_interview_async(str(live.interview.id), notify=False)

    await db_session.refresh(live.interview)
    assert live.interview.ai_score == 66
    assert ai.score_interview_transcript.await_args.kwargs["scoring_profile"] is None


@pytest.mark.asyncio
async def test_the_detail_the_employer_reads_carries_the_report(client, db_session, monkeypatch):
    interview = await strict_with_profile(db_session, monkeypatch)
    _mock_anthropic_service(monkeypatch, result=scoring_result(4, None, 5, 4, 5, 3))
    await interviews_tasks._transcribe_and_score_interview_async(str(interview.interview.id), notify=False)
    from app.modules.interviews import service as service_module

    storage = MagicMock()
    storage.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: storage)

    resp = await client.get(
        "/api/v1/interviews/detail",
        params={"job_id": str(interview.job.id), "talent_pool_profile_id": str(interview.interview.talent_pool_profile_id)},
        headers=headers(interview.employer),
    )

    body = resp.json()
    assert resp.status_code == 200 and body["ai_score"] is None
    report = body["score_report"]
    assert report["complete"] is False and report["unassessed"] == ["P&L"] and report["score"] is None
    assert report["points"] == 68 and report["assessed_weight"] == 80
    assert [row["name"] for row in report["rows"]] == [c["name"] for c in COMPETENCIES]


@pytest.mark.asyncio
async def test_an_interview_without_a_report_has_none(client, db_session, monkeypatch):
    from app.modules.interviews import service as service_module
    from app.modules.interviews.enums import InterviewStatus

    plain = await make_strict(db_session, status=InterviewStatus.SCORED.value, transcript="AI: q\n\nCandidate: a")
    storage = MagicMock()
    storage.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: storage)

    resp = await client.get(
        "/api/v1/interviews/detail",
        params={"job_id": str(plain.job.id), "talent_pool_profile_id": str(plain.interview.talent_pool_profile_id)},
        headers=headers(plain.employer),
    )

    assert resp.status_code == 200 and resp.json()["score_report"] is None
