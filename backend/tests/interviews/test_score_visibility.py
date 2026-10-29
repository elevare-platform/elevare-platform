"""The per-job switch for the interview score and provisional band (docs/08_DECISIONS.md, item 54).

Off for a job: its employer and the shared link are not sent the total, the band, the practical
case's total or the assessment lines that state them. The competency ratings and the evidence stay.
Its employer or an Elevare admin can flip it; an admin always sees the real values; other jobs are
not affected."""

import pytest
from sqlalchemy import select

from app.modules.interviews.assessment_text import weighted_lines
from app.modules.interviews.models import InterviewWeightedScore, JobScoreVisibility
from app.modules.interviews.score_visibility import hide_scores, strip_score_lines
from app.modules.interviews.service import InterviewService
from tests.conftest import make_employer, make_organization_for

from .test_score_review import (
    an_admin,
    detail,
    headers,
    review_url,
    scored_at,
    text_for,
    with_ratings,
)

PRACTICAL = {
    "question_number": 9,
    "rows": [{"key": "prioritisation", "name": "Prioritisation", "weight": 100, "rating": 4, "rationale": ""}],
    "complete": True,
    "score": 4.0,
    "assessed_weight": 100,
    "total_weight": 100,
    "unassessed": [],
    "summary": "",
}


def visibility_url(job):
    return f"/api/v1/interviews/jobs/{job.id}/score-visibility"


async def scored_with_text(db_session, score=60):
    """A scored interview whose stored report, written assessment and practical case all state the score."""
    interview = await scored_at(db_session, score)
    report = with_ratings()
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = {**report, "practical": PRACTICAL}
    interview.interview.ai_score = report["score"]
    interview.interview.ai_rationale = text_for(report) + "\n\nPractical case: 4 of 5. On its own.\n- Prioritisation (100%): 4 of 5."
    await db_session.commit()
    return interview


# ── What is left out ─────────────────────────────────────────────────────────────


def test_the_lines_that_state_a_score_a_band_or_a_recommendation_are_dropped_and_the_rest_kept():
    report = with_ratings()
    text = (
        "A steady candidate.\n\n"
        + "\n".join(weighted_lines(report))
        + "\n\nCompetency scores (1 to 5):\n- Strategy (weight 60%, key): 3 of 5 (Competent).\n\n"
        "Practical case: 4 of 5. On its own.\n- Prioritisation (100%): 4 of 5.\n\nStrengths:\n- Clear"
    )

    cleaned = strip_score_lines(text)

    for gone in ("Weighted score", "Suggested band", "Practical case: 4 of 5"):
        assert gone not in cleaned
    for kept in ("A steady candidate.", "- Strategy (weight 60%, key): 3 of 5", "- Prioritisation (100%): 4 of 5.", "- Clear"):
        assert kept in cleaned
    assert "\n\n\n" not in cleaned


def test_an_incomplete_score_a_recommendation_and_a_held_band_note_are_dropped_too():
    text = (
        "Summary.\n\nINCOMPLETE SCORE: 48 of 60 weighted points could be assessed.\n\n"
        "Overall recommendation: Hold\n\n"
        "Key competency rated under 3 of 5: Strategy. The band is held at Hold for evidence until a person has looked at it."
    )

    assert strip_score_lines(text) == "Summary."


def test_a_key_competency_note_that_does_not_mention_the_band_stays():
    text = "Summary.\n\nKey competency rated under 3 of 5: Strategy."

    assert strip_score_lines(text) == text


def test_hiding_keeps_the_rows_and_ratings_and_flags_the_report():
    hidden = hide_scores(rationale="Weighted score: 60 of 100.", report=with_ratings(), practical=PRACTICAL)

    assert hidden.score is None and hidden.rationale == ""
    assert (hidden.report["hidden"], hidden.report["score"], hidden.report["band"], hidden.report["bands"]) == (True, None, None, {})
    assert [row["rating"] for row in hidden.report["rows"]] == [3, 3]
    assert (hidden.practical["hidden"], hidden.practical["score"]) == (True, None)
    assert hidden.practical["rows"][0]["rating"] == 4


def test_hiding_nothing_stays_nothing():
    hidden = hide_scores(rationale=None, report=None, practical=None)

    assert (hidden.rationale, hidden.report, hidden.practical) == (None, None, None)


# ── The switch ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_job_shows_its_scores_until_somebody_switches_them_off(client, db_session):
    interview = await scored_with_text(db_session)

    state = await client.get(visibility_url(interview.job), headers=headers(interview.employer))
    body = await detail(client, interview, interview.employer)

    assert state.json() == {"show_scores": True}
    assert body["ai_score"] == 60 and body["scores_hidden"] is False
    assert body["score_report"]["band"] == "Do not shortlist" and body["practical_case"]["score"] == 4.0


@pytest.mark.asyncio
async def test_the_owner_switches_the_scores_off_and_the_employer_is_not_sent_them(client, db_session):
    interview = await scored_with_text(db_session)

    resp = await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(interview.employer))
    body = await detail(client, interview, interview.employer)

    assert resp.json() == {"show_scores": False}
    assert body["scores_hidden"] is True and body["ai_score"] is None and body["reviewed"] is False
    report = body["score_report"]
    assert (report["hidden"], report["score"], report["band"]) == (True, None, None)
    assert [row["rating"] for row in report["rows"]] == [3, 3]
    assert body["practical_case"]["score"] is None and body["practical_case"]["hidden"] is True
    for gone in ("Weighted score", "Suggested band", "Practical case:"):
        assert gone not in body["ai_rationale"]
    assert "- Strategy (weight 60%, key): 3 of 5" in body["ai_rationale"]
    # Nothing in the reply states the total or the band.
    assert "Do not shortlist" not in str(body["ai_rationale"]) + str(report)


@pytest.mark.asyncio
async def test_the_shared_link_is_sent_no_scores_either(db_session):
    from app.modules.jobs.repository import JobRepository

    interview = await scored_with_text(db_session)
    job_id, profile_id = interview.job.id, interview.interview.talent_pool_profile_id
    service = InterviewService(db_session)
    try:
        await service.set_score_visibility(interview.employer, job_id, False)
        job = await JobRepository(db_session).get_by_id(job_id)
        row = await service._repo.get_by_job_and_profile(job_id, profile_id)
        shared = await service.build_detail(job, row, include_panel_decision=False)
    finally:
        await service.close()

    assert shared.ai_score is None and shared.scores_hidden is True
    assert shared.score_report.hidden is True and shared.score_report.band is None
    assert "Weighted score" not in shared.ai_rationale


@pytest.mark.asyncio
async def test_a_reviewed_score_is_hidden_too_and_shows_no_reviewed_tag_while_off(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))
    await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(interview.employer))

    body = await detail(client, interview, interview.employer)

    assert body["ai_score"] is None and body["reviewed"] is False
    assert "89" not in str(body["ai_rationale"]) and "Strong shortlist" not in str(body)


@pytest.mark.asyncio
async def test_switching_back_on_shows_everything_again(client, db_session):
    interview = await scored_with_text(db_session)
    await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(interview.employer))

    await client.put(visibility_url(interview.job), json={"show_scores": True}, headers=headers(interview.employer))
    body = await detail(client, interview, interview.employer)

    assert body["scores_hidden"] is False and body["ai_score"] == 60
    assert "Weighted score: 60 of 100" in body["ai_rationale"]
    rows = (await db_session.execute(select(JobScoreVisibility))).scalars().all()
    assert len(rows) == 1 and rows[0].show_scores is True  # one row per job, updated in place


@pytest.mark.asyncio
async def test_an_admin_always_sees_the_real_scores_and_the_admin_list_keeps_them(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(interview.employer))

    body = await detail(client, interview, admin)
    listed = (await client.get(f"/api/v1/interview-list?job_id={interview.job.id}", headers=headers(admin))).json()["items"][0]

    assert body["scores_hidden"] is False and body["ai_score"] == 60 and body["score_report"]["band"] == "Do not shortlist"
    assert listed["interview_score"] == 60


@pytest.mark.asyncio
async def test_the_switch_is_per_job(client, db_session):
    off = await scored_with_text(db_session)
    other = await scored_at(db_session, 58)  # another job, never switched
    await client.put(visibility_url(off.job), json={"show_scores": False}, headers=headers(off.employer))

    still_on = await detail(client, other, other.employer)

    assert still_on["ai_score"] == 58 and still_on["scores_hidden"] is False


# ── Who may flip it ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_teammate_and_an_admin_may_flip_it_but_a_stranger_and_a_candidate_may_not(client, db_session):
    from .test_interview_router import register_and_promote

    interview = await scored_with_text(db_session)
    organization = await make_organization_for(db_session, interview.employer, company_name="Acme")
    teammate = make_employer(organization_id=organization.id)
    stranger = make_employer()
    db_session.add_all([teammate, stranger])
    admin = await an_admin(db_session)
    await db_session.commit()
    token, _ = await register_and_promote(client, db_session, "CANDIDATE")

    for who in (headers(stranger), {"Authorization": f"Bearer {token}"}, {}):
        assert (await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=who)).status_code in (401, 403)
        assert (await client.get(visibility_url(interview.job), headers=who)).status_code in (401, 403)
    by_teammate = await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(teammate))
    by_admin = await client.put(visibility_url(interview.job), json={"show_scores": True}, headers=headers(admin))

    assert by_teammate.status_code == 200 and by_admin.status_code == 200
    saved = (await db_session.execute(select(JobScoreVisibility))).scalar_one()
    assert saved.changed_by == admin.id


@pytest.mark.asyncio
async def test_an_unknown_job_is_not_found(client, db_session):
    from uuid import uuid4

    interview = await scored_with_text(db_session)

    resp = await client.put(
        f"/api/v1/interviews/jobs/{uuid4()}/score-visibility", json={"show_scores": False}, headers=headers(interview.employer)
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_the_request_needs_a_true_or_false(client, db_session):
    interview = await scored_with_text(db_session)

    for bad in ({}, {"show_scores": "maybe"}, {"show_scores": None}):
        resp = await client.put(visibility_url(interview.job), json=bad, headers=headers(interview.employer))
        assert resp.status_code == 422
