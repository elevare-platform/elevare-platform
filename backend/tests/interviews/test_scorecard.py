"""The interview scorecard, laid out as Elevare's printed scorecard (docs/08_DECISIONS.md, item 56).

The worked example is Ehi Okpepe's scorecard for the National Sales Manager role: six competencies
with weights 30, 25, 15, 15, 10 and 5, rated 4, 4, 3.5, 3.5, 3.5 and 3, whose points (rating times
weight over ten) add up to 37.5 out of 50, which is 75 out of 100."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.modules.interviews import service as service_module
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import InterviewScoreReview, InterviewWeightedScore
from app.modules.interviews.scorecard import build_scorecard, system_evidence
from app.modules.interviews.scoring_profile import normalise, weighted_report
from app.modules.interviews.service import InterviewService

from .test_score_review import an_admin, detail, headers, review_url, scored_at
from .test_score_visibility import visibility_url
from .test_strict_interview import make_strict

PROFILE = [
    {"name": "Route-to-market and distributor development", "weight": 30, "key": True},
    {"name": "Sales execution and territory management", "weight": 25, "key": True},
    {"name": "Sales-force leadership", "weight": 15, "key": False},
    {"name": "Revenue, margin and collections management", "weight": 15, "key": False},
    {"name": "Forecasting and supply coordination", "weight": 10, "key": False},
    {"name": "Reporting and performance analytics", "weight": 5, "key": False},
]
RATINGS = [4, 4, 3.5, 3.5, 3.5, 3]
EVIDENCE = [
    "Strong localized knowledge (Lagos mapping, Epe/Ikorodu corridor pilot, Joint Business Plans).",
    "Focused on numeric and weighted distribution, line-per-call and strike rates.",
    "",
    "Emphasised high-margin product focus during COVID and collections within 30 days.",
    "",
    "",
]


def pdf_report():
    rated = [
        {"name": item["name"], "score": rating, "coverage": "FULLY_ASSESSED", "scorecard_evidence": evidence,
         "rationale": "Reason.", "evidence": "A summary of what was done.", "verify": "The pilot's results."}
        for item, rating, evidence in zip(PROFILE, RATINGS, EVIDENCE, strict=True)
    ]
    return weighted_report(normalise(rated, PROFILE))


def card(**kwargs):
    report = kwargs.pop("report", pdf_report())
    defaults = {
        "report": report,
        "practical": None,
        "admin": None,
        "top_strengths": ["Excellent grasp of the terrain."],
        "panel_decision": None,
        "total": (report or {}).get("score"),
        "hidden": False,
    }
    return build_scorecard(**{**defaults, **kwargs})


# ── The layout and the points ────────────────────────────────────────────────────


def test_the_worked_example_gives_the_printed_points_and_totals():
    scorecard = card()

    assert [row["points"] for row in scorecard["rows"]] == [12.0, 10.0, 5.25, 5.25, 3.5, 1.5]
    assert (scorecard["total_points"], scorecard["max_points"], scorecard["total_score"]) == (37.5, 50.0, 75)


def test_the_points_total_is_the_hundred_point_total_halved():
    scorecard = card()

    assert scorecard["total_points"] * 2 == scorecard["total_score"]


def test_each_row_carries_its_weight_rating_and_key_mark():
    first = card()["rows"][0]

    assert (first["name"], first["weight"], first["rating"], first["key"]) == (
        "Route-to-market and distributor development", 30, 4, True,
    )


def test_an_interview_without_competencies_has_no_scorecard():
    assert card(report=None) is None
    assert card(report={"rows": []}) is None


def test_a_competency_that_was_not_assessed_earns_no_points_and_the_total_follows_the_rows_that_were():
    report = pdf_report()
    report["rows"][5]["rating"] = None

    scorecard = card(report=report)

    assert scorecard["rows"][5]["points"] is None and scorecard["rows"][5]["evidence"] == ""
    assert scorecard["total_points"] == 36.0


# ── The Evidence / Verification column ───────────────────────────────────────────


def test_the_evidence_is_the_systems_scorecard_evidence_when_it_wrote_one():
    assert card()["rows"][0]["evidence"] == EVIDENCE[0]


def test_an_older_interview_gets_its_evidence_from_what_was_stored_with_what_to_verify():
    row = {"rating": 4, "evidence": "Mapped Lagos and ran a corridor pilot.", "rationale": "Reason.", "verify": "The pilot's results."}

    assert system_evidence(row) == "Mapped Lagos and ran a corridor pilot. To verify: The pilot's results."
    assert system_evidence({"rating": 4, "rationale": "Only a reason."}) == "Only a reason."
    assert system_evidence({"rating": None, "evidence": "x"}) == ""


def test_the_scorecard_evidence_is_not_given_the_to_verify_line_twice():
    row = {"rating": 4, "scorecard_evidence": "Lagos mapping. To verify: the pilot.", "verify": "The pilot."}

    assert system_evidence(row) == "Lagos mapping. To verify: the pilot."


def test_an_admins_evidence_replaces_the_systems_for_that_competency_only():
    admin = {"evidence": {"Route-to-market and distributor development": "  Written   by hand. "}}

    rows = card(admin=admin)["rows"]

    assert rows[0]["evidence"] == "Written by hand." and rows[1]["evidence"] == EVIDENCE[1]


# ── The summary ──────────────────────────────────────────────────────────────────


def test_the_strengths_are_the_systems_top_strengths_or_the_admins_own_lines():
    assert card()["strengths"] == ["Excellent grasp of the terrain."]
    assert card(admin={"strengths": "First line.\n\n  Second line.  "})["strengths"] == ["First line.", "Second line."]


def test_the_practical_rating_is_the_systems_case_score_or_the_admins_own():
    practical = {"complete": True, "score": 4.0}

    assert card(practical=practical)["practical_rating"] == 4.0
    assert card(practical=practical, admin={"practical_rating": 3.5})["practical_rating"] == 3.5
    assert card(practical={"complete": False, "score": None})["practical_rating"] is None
    assert card()["practical_rating"] is None


def test_the_decision_is_the_admins_wording_with_the_panels_band_beside_it():
    scorecard = card(admin={"decision": "Proceed to Final Interview / Offer Consideration"}, panel_decision="Shortlist")

    assert scorecard["decision"] == "Proceed to Final Interview / Offer Consideration"
    assert scorecard["panel_decision"] == "Shortlist"
    assert card()["decision"] is None


def test_a_total_that_was_typed_is_the_one_shown_beside_the_points():
    scorecard = card(total=89)

    assert scorecard["total_score"] == 89 and scorecard["total_points"] == 37.5


# ── When the job's scores are off ────────────────────────────────────────────────


def test_with_scores_off_the_points_and_totals_and_practical_rating_are_left_out_but_the_rest_stays():
    scorecard = card(hidden=True, practical={"complete": True, "score": 4.0}, admin={"decision": "Proceed.", "practical_rating": 4.5})

    assert all(row["points"] is None for row in scorecard["rows"])
    assert (scorecard["total_points"], scorecard["total_score"], scorecard["practical_rating"]) == (None, None, None)
    assert scorecard["rows"][0]["rating"] == 4 and scorecard["rows"][0]["evidence"] == EVIDENCE[0]
    assert scorecard["strengths"] and scorecard["decision"] == "Proceed." and scorecard["hidden"] is True


# ── Through the API ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: fake)


async def scored_like_the_example(db_session):
    interview = await scored_at(db_session, 75)
    report = pdf_report()
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = {**report, "record": {"strengths": ["Excellent grasp of the terrain.", "Strong on execution metrics."]}}
    interview.interview.ai_score = report["score"]
    await db_session.commit()
    return interview


@pytest.mark.asyncio
async def test_the_detail_carries_the_scorecard_for_the_employer(client, db_session):
    interview = await scored_like_the_example(db_session)

    body = await detail(client, interview, interview.employer)

    scorecard = body["scorecard"]
    assert (scorecard["total_points"], scorecard["max_points"], scorecard["total_score"]) == (37.5, 50.0, 75)
    assert scorecard["rows"][0]["evidence"] == EVIDENCE[0]
    assert scorecard["strengths"] == ["Excellent grasp of the terrain.", "Strong on execution metrics."]


@pytest.mark.asyncio
async def test_an_interview_scored_without_competencies_has_no_scorecard(client, db_session):
    interview = await make_strict(db_session, status=InterviewStatus.SCORED.value, transcript="x")
    interview.interview.ai_score = 70
    interview.interview.completed_at = datetime.now(UTC)
    await db_session.commit()

    assert (await detail(client, interview, interview.employer))["scorecard"] is None


@pytest.mark.asyncio
async def test_the_shared_link_is_given_the_same_scorecard(db_session):
    from app.modules.jobs.repository import JobRepository

    interview = await scored_like_the_example(db_session)
    job_id, profile_id = interview.job.id, interview.interview.talent_pool_profile_id
    service = InterviewService(db_session)
    try:
        job = await JobRepository(db_session).get_by_id(job_id)
        row = await service._repo.get_by_job_and_profile(job_id, profile_id)
        shared = await service.build_detail(job, row, include_panel_decision=False)
    finally:
        await service.close()

    assert shared.scorecard["total_points"] == 37.5 and shared.scorecard["panel_decision"] is None


@pytest.mark.asyncio
async def test_an_admin_fills_the_scorecard_by_hand_and_everyone_reads_it(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    body = {
        "scorecard": {
            "evidence": {"sales-force leadership": "Restructured teams after the merger and ran sales training."},
            "practical_rating": 4,
            "strengths": "Excellent practical grasp of the Nigerian terrain.\nStrong emphasis on strike rates.",
            "decision": "Proceed to Final Interview / Offer Consideration",
        }
    }

    resp = await client.put(review_url(interview), json=body, headers=headers(admin))

    assert resp.status_code == 200 and resp.json()["reviewed"] is True and resp.json()["score"] == 75
    seen = (await detail(client, interview, interview.employer))["scorecard"]
    assert seen["rows"][2]["evidence"] == "Restructured teams after the merger and ran sales training."
    assert seen["rows"][2]["points"] == 5.25 and seen["rows"][0]["evidence"] == EVIDENCE[0]
    assert seen["practical_rating"] == 4
    assert seen["strengths"] == ["Excellent practical grasp of the Nigerian terrain.", "Strong emphasis on strike rates."]
    assert seen["decision"] == "Proceed to Final Interview / Offer Consideration"
    saved = (await db_session.execute(select(InterviewScoreReview))).scalar_one()
    assert saved.scorecard["evidence"] == {"Sales-force leadership": "Restructured teams after the merger and ran sales training."}


@pytest.mark.asyncio
async def test_the_scorecard_fields_alone_are_a_review_and_the_history_says_so(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    await client.put(review_url(interview), json={"scorecard": {"decision": "Hold."}}, headers=headers(admin))
    history = (await detail(client, interview, admin))["score_review"]

    assert history["reviews"][0]["scorecard_changed"] is True
    assert history["original_evidence"]["Route-to-market and distributor development"] == EVIDENCE[0]


@pytest.mark.asyncio
async def test_bad_scorecard_fields_are_refused_and_nothing_is_saved(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    unknown = await client.put(review_url(interview), json={"scorecard": {"evidence": {"Charisma": "x"}}}, headers=headers(admin))
    long_text = await client.put(
        review_url(interview), json={"scorecard": {"evidence": {"Sales-force leadership": "x" * 1001}}}, headers=headers(admin)
    )
    practical = await client.put(review_url(interview), json={"scorecard": {"practical_rating": 3.3}}, headers=headers(admin))
    empty = await client.put(review_url(interview), json={"scorecard": {"decision": "   ", "strengths": ""}}, headers=headers(admin))
    too_long_decision = await client.put(review_url(interview), json={"scorecard": {"decision": "x" * 301}}, headers=headers(admin))

    assert unknown.json()["code"] == "UNKNOWN_COMPETENCY"
    assert long_text.json()["code"] == "EVIDENCE_TOO_LONG"
    assert practical.json()["code"] == "INVALID_RATING"
    assert empty.json()["code"] == "NOTHING_TO_REVIEW"
    assert too_long_decision.status_code == 422
    assert (await db_session.execute(select(InterviewScoreReview))).scalars().all() == []


@pytest.mark.asyncio
async def test_only_an_admin_can_fill_the_scorecard(client, db_session):
    interview = await scored_like_the_example(db_session)

    resp = await client.put(review_url(interview), json={"scorecard": {"decision": "Go."}}, headers=headers(interview.employer))

    assert resp.status_code == 403
    assert (await db_session.execute(select(InterviewScoreReview))).scalars().all() == []


@pytest.mark.asyncio
async def test_half_point_ratings_can_be_set_by_an_admin_and_move_the_points(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.put(
        review_url(interview), json={"ratings": {"Reporting and performance analytics": 4.5}}, headers=headers(admin)
    )
    scorecard = (await detail(client, interview, interview.employer))["scorecard"]

    assert resp.status_code == 200
    assert scorecard["rows"][5]["rating"] == 4.5 and scorecard["rows"][5]["points"] == 2.25
    assert scorecard["total_points"] == 38.25
    refused = await client.put(
        review_url(interview), json={"ratings": {"Reporting and performance analytics": 3.3}}, headers=headers(admin)
    )
    assert refused.json()["code"] == "INVALID_RATING"


@pytest.mark.asyncio
async def test_with_the_jobs_scores_off_the_employers_scorecard_has_no_points_or_totals(client, db_session):
    interview = await scored_like_the_example(db_session)
    await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(interview.employer))

    body = await detail(client, interview, interview.employer)

    assert body["scorecard"]["hidden"] is True and body["scorecard"]["total_points"] is None
    assert all(row["points"] is None and row["rating"] is not None for row in body["scorecard"]["rows"])
    assert body["scorecard"]["rows"][0]["evidence"] == EVIDENCE[0]


# ── The Evaluation Summary switch (docs/08_DECISIONS.md, item 57) ────────────────


def summary_url(job):
    return f"/api/v1/interviews/jobs/{job.id}/scorecard-summary"


def test_with_the_summary_off_the_practical_rating_strengths_and_decision_are_left_out_for_everyone():
    scorecard = card(
        show_summary=False,
        practical={"complete": True, "score": 4.0},
        admin={"decision": "Proceed.", "practical_rating": 4.5, "strengths": "Sharp."},
        panel_decision="Strong Shortlist",
    )

    assert (scorecard["practical_rating"], scorecard["strengths"], scorecard["decision"], scorecard["panel_decision"]) == (
        None, [], None, None,
    )
    assert scorecard["show_summary"] is False
    assert scorecard["total_points"] == 37.5 and scorecard["rows"][0]["evidence"] == EVIDENCE[0]


def test_the_summary_is_on_unless_switched_off():
    assert card(admin={"decision": "Proceed."})["show_summary"] is True


@pytest.mark.asyncio
async def test_only_an_admin_can_switch_the_summary_and_everyone_reads_the_result(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    body = {"show_summary": False}

    for who in (headers(interview.employer), {}):
        assert (await client.put(summary_url(interview.job), json=body, headers=who)).status_code in (401, 403)
        assert (await client.get(summary_url(interview.job), headers=who)).status_code in (401, 403)
    by_admin = await client.put(summary_url(interview.job), json=body, headers=headers(admin))

    assert by_admin.status_code == 200 and by_admin.json() == {"show_summary": False}
    assert (await client.get(summary_url(interview.job), headers=headers(admin))).json() == {"show_summary": False}
    for who in (interview.employer, admin):
        seen = (await detail(client, interview, who))["scorecard"]
        assert seen["show_summary"] is False and seen["strengths"] == [] and seen["decision"] is None
    await client.put(summary_url(interview.job), json={"show_summary": True}, headers=headers(admin))
    assert (await detail(client, interview, interview.employer))["scorecard"]["strengths"]


@pytest.mark.asyncio
async def test_the_summary_switch_needs_a_true_or_false_and_a_real_job(client, db_session):
    from uuid import uuid4

    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    for bad in ({}, {"show_summary": "maybe"}, {"show_summary": None}):
        assert (await client.put(summary_url(interview.job), json=bad, headers=headers(admin))).status_code == 422
    missing = await client.put(
        f"/api/v1/interviews/jobs/{uuid4()}/scorecard-summary", json={"show_summary": False}, headers=headers(admin)
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_the_summary_switch_leaves_the_scores_switch_alone_and_the_other_way_round(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    await client.put(summary_url(interview.job), json={"show_summary": False}, headers=headers(admin))
    await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(admin))
    await client.put(visibility_url(interview.job), json={"show_scores": True}, headers=headers(admin))

    assert (await client.get(summary_url(interview.job), headers=headers(admin))).json() == {"show_summary": False}
    assert (await client.get(visibility_url(interview.job), headers=headers(admin))).json() == {"show_scores": True}


@pytest.mark.asyncio
async def test_what_an_admin_filled_in_survives_a_save_made_while_the_summary_is_off(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(
        review_url(interview),
        json={"scorecard": {"decision": "Proceed.", "strengths": "Sharp.", "practical_rating": 4}},
        headers=headers(admin),
    )
    await client.put(summary_url(interview.job), json={"show_summary": False}, headers=headers(admin))

    saved = await client.put(
        review_url(interview),
        json={"scorecard": {"evidence": {"sales-force leadership": "Ran the training."}}},
        headers=headers(admin),
    )
    await client.put(summary_url(interview.job), json={"show_summary": True}, headers=headers(admin))

    assert saved.status_code == 200
    seen = (await detail(client, interview, interview.employer))["scorecard"]
    assert (seen["decision"], seen["strengths"], seen["practical_rating"]) == ("Proceed.", ["Sharp."], 4)
    assert seen["rows"][2]["evidence"] == "Ran the training."


@pytest.mark.asyncio
async def test_removing_a_review_while_the_summary_is_off_still_clears_the_summary_fields(client, db_session):
    interview = await scored_like_the_example(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"scorecard": {"decision": "Proceed."}}, headers=headers(admin))
    await client.put(summary_url(interview.job), json={"show_summary": False}, headers=headers(admin))

    cleared = await client.delete(review_url(interview), headers=headers(admin))
    await client.put(summary_url(interview.job), json={"show_summary": True}, headers=headers(admin))

    assert cleared.status_code == 200
    assert (await detail(client, interview, interview.employer))["scorecard"]["decision"] is None
