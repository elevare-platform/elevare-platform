"""The per-job switches for the score number, the gaps and risks and the written assessment
(docs/08_DECISIONS.md, item 61).

An Elevare admin can turn each off for a job. An employer and the shared link are then not sent that
part; the band and the 1 to 5 ratings stay when only the number is off; an admin always sees everything."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.modules.interviews import service as service_module
from app.modules.interviews.models import InterviewWeightedScore
from app.modules.interviews.score_visibility import (
    hide_numbers,
    strip_gaps,
    strip_numbers,
)

from .test_score_review import an_admin, detail, headers
from .test_score_visibility import visibility_url
from .test_scorecard import scored_like_the_example

TEXT = (
    "A steady candidate.\n\n"
    "Weighted score: 75 of 100. Suggested band (provisional): Shortlist.\n\n"
    "Competency scores (1 to 5):\n- Strategy (weight 60%, key): 4 of 5 (Strong).\n\n"
    "Practical case: 3.8 of 5. This is reported on its own and is not part of the weighted score.\n"
    "- Plan (50%): 4 of 5. Good.\n\n"
    "Strengths:\n- Clear route to market.\n\n"
    "Gaps and risks:\n- Thin on forecasting.\n- Little on analytics.\n\n"
    "Claims requiring validation:\n- A pilot's results."
)


def display_url(job):
    return f"/api/v1/interviews/jobs/{job.id}/result-display"


# ── The text and report helpers ──────────────────────────────────────────────────


def test_the_gaps_block_is_taken_out_of_the_text_and_the_rest_stays():
    out = strip_gaps(TEXT)

    assert "Gaps and risks" not in out and "Thin on forecasting" not in out
    assert "Strengths:\n- Clear route to market." in out
    assert "Claims requiring validation:\n- A pilot's results." in out
    assert "\n\n\n" not in out


def test_the_gaps_block_at_the_very_end_is_taken_out_too():
    assert strip_gaps("Strengths:\n- A.\n\nGaps and risks:\n- B.") == "Strengths:\n- A."


def test_the_total_goes_from_the_text_but_the_band_the_ratings_and_the_criteria_stay():
    out = strip_numbers(TEXT)

    assert "75 of 100" not in out and "Practical case: 3.8" not in out
    assert "Suggested band (provisional): Shortlist." in out
    assert "Strategy (weight 60%, key): 4 of 5 (Strong)." in out
    assert "- Plan (50%): 4 of 5. Good." in out


def test_an_incomplete_score_line_with_point_counts_goes():
    out = strip_numbers("Summary.\n\nINCOMPLETE SCORE: 70 of 100 weighted points could be assessed. A person decides.")

    assert out == "Summary."


def test_hiding_the_numbers_keeps_the_band_and_the_rows_and_drops_the_total_and_cut_offs():
    report = {"rows": [{"name": "A", "weight": 100, "rating": 4}], "score": 80, "band": "Shortlist",
              "points": 80.0, "bands": {"strong": 85, "shortlist": 75, "hold": 65}, "complete": True}

    hidden = hide_numbers(rationale=TEXT, report=report, practical={"score": 3.8, "rows": []})

    assert hidden.report["band"] == "Shortlist" and hidden.report["rows"] == report["rows"]
    assert (hidden.report["score"], hidden.report["bands"], hidden.report["number_hidden"]) == (None, {}, True)
    assert hidden.practical["score"] is None and hidden.practical["number_hidden"] is True
    assert hidden.score is None


# ── The switch itself ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: fake)


async def scored_with_text(db_session):
    """The worked example interview, with a written assessment that has gaps and a record that lists them."""
    interview = await scored_like_the_example(db_session)
    interview.interview.ai_rationale = TEXT
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = {
        **row.report,
        "record": {"strengths": ["Excellent grasp of the terrain."], "gaps": ["Thin on forecasting."]},
    }
    await db_session.commit()
    return interview


@pytest.mark.asyncio
async def test_all_three_are_on_until_an_admin_switches_one_off(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.get(display_url(interview.job), headers=headers(admin))

    assert resp.status_code == 200
    assert resp.json() == {"show_score_number": True, "show_gaps": True, "show_writeup": True}


@pytest.mark.asyncio
async def test_only_an_admin_can_read_or_change_it(client, db_session):
    interview = await scored_with_text(db_session)
    await db_session.commit()

    for who in (headers(interview.employer), {}):
        assert (await client.get(display_url(interview.job), headers=who)).status_code in (401, 403)
        assert (await client.put(display_url(interview.job), json={"show_gaps": False}, headers=who)).status_code in (401, 403)


@pytest.mark.asyncio
async def test_only_the_fields_sent_change_and_nothing_sent_is_refused(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    first = await client.put(display_url(interview.job), json={"show_gaps": False}, headers=headers(admin))
    second = await client.put(display_url(interview.job), json={"show_writeup": False}, headers=headers(admin))
    empty = await client.put(display_url(interview.job), json={}, headers=headers(admin))

    assert first.json() == {"show_score_number": True, "show_gaps": False, "show_writeup": True}
    assert second.json() == {"show_score_number": True, "show_gaps": False, "show_writeup": False}
    assert (empty.status_code, empty.json()["code"]) == (422, "NOTHING_TO_CHANGE")


@pytest.mark.asyncio
async def test_a_bad_value_or_an_unknown_job_is_refused(client, db_session):
    from uuid import uuid4

    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    bad = await client.put(display_url(interview.job), json={"show_gaps": "maybe"}, headers=headers(admin))
    missing = await client.put(
        f"/api/v1/interviews/jobs/{uuid4()}/result-display", json={"show_gaps": False}, headers=headers(admin)
    )

    assert bad.status_code == 422 and missing.status_code == 404


@pytest.mark.asyncio
async def test_the_three_switches_leave_the_scores_and_summary_switches_alone(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()

    await client.put(display_url(interview.job), json={"show_score_number": False, "show_gaps": False}, headers=headers(admin))

    assert (await client.get(visibility_url(interview.job), headers=headers(admin))).json() == {"show_scores": True}
    assert (await client.get(f"/api/v1/interviews/jobs/{interview.job.id}/scorecard-summary", headers=headers(admin))).json() == {
        "show_summary": True
    }


# ── The score number off ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_with_the_number_off_the_employer_gets_the_band_and_ratings_but_no_total_or_points(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(display_url(interview.job), json={"show_score_number": False}, headers=headers(admin))

    body = await detail(client, interview, interview.employer)

    assert body["score_number_hidden"] is True and body["scores_hidden"] is False
    assert body["ai_score"] is None
    report = body["score_report"]
    assert report["score"] is None and report["bands"] == {} and report["number_hidden"] is True
    assert report["band"] == "Shortlist"
    assert [row["rating"] for row in report["rows"]] == [4, 4, 3.5, 3.5, 3.5, 3]
    assert "75 of 100" not in body["ai_rationale"] and "Suggested band (provisional): Shortlist" in body["ai_rationale"]
    assert body["practical_case"] is None or body["practical_case"]["score"] is None
    sheet = body["scorecard"]
    assert sheet["hidden"] is True and sheet["total_points"] is None and sheet["total_score"] is None
    assert all(row["points"] is None and row["rating"] is not None for row in sheet["rows"])


@pytest.mark.asyncio
async def test_an_admin_still_sees_the_numbers(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(
        display_url(interview.job),
        json={"show_score_number": False, "show_gaps": False, "show_writeup": False},
        headers=headers(admin),
    )

    body = await detail(client, interview, admin)

    assert body["score_number_hidden"] is False and body["gaps_hidden"] is False and body["writeup_hidden"] is False
    assert body["ai_score"] == 75 and body["score_report"]["score"] == 75
    assert "Gaps and risks:" in body["ai_rationale"]
    assert body["record"]["top_gaps"] == ["Thin on forecasting."]
    assert body["scorecard"]["total_score"] == 75


@pytest.mark.asyncio
async def test_with_the_scores_switched_off_altogether_the_band_is_gone_too(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(display_url(interview.job), json={"show_score_number": False}, headers=headers(admin))
    await client.put(visibility_url(interview.job), json={"show_scores": False}, headers=headers(admin))

    body = await detail(client, interview, interview.employer)

    assert body["scores_hidden"] is True and body["score_number_hidden"] is False
    assert body["score_report"]["band"] is None


async def shared_detail_for(db_session, interview):
    """The detail the shared link is built from: no admin history, no panel decision."""
    from app.modules.interviews.service import InterviewService
    from app.modules.jobs.repository import JobRepository

    service = InterviewService(db_session)
    try:
        job = await JobRepository(db_session).get_by_id(interview.job.id)
        row = await service._repo.get_by_job_and_profile(interview.job.id, interview.interview.talent_pool_profile_id)
        return await service.build_detail(job, row, include_panel_decision=False)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_the_shared_link_gets_the_same_number_off_result(db_session, client):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(display_url(interview.job), json={"show_score_number": False}, headers=headers(admin))

    shared = await shared_detail_for(db_session, interview)

    assert shared.score_number_hidden is True and shared.ai_score is None
    assert shared.score_report.band == "Shortlist" and shared.score_report.score is None


# ── The gaps and risks off ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_with_the_gaps_off_the_card_and_the_text_block_are_gone_but_the_rest_stays(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(display_url(interview.job), json={"show_gaps": False}, headers=headers(admin))

    body = await detail(client, interview, interview.employer)

    assert body["gaps_hidden"] is True
    assert body["record"]["top_gaps"] == []
    assert "Gaps and risks" not in body["ai_rationale"] and "Thin on forecasting" not in body["ai_rationale"]
    assert "Clear route to market." in body["ai_rationale"] and "Claims requiring validation" in body["ai_rationale"]
    assert body["record"]["top_strengths"] and body["ai_score"] == 75


# ── The written assessment off ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_with_the_write_up_off_the_text_is_not_sent_but_the_band_ratings_and_scorecard_are(client, db_session):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(display_url(interview.job), json={"show_writeup": False}, headers=headers(admin))

    body = await detail(client, interview, interview.employer)

    assert body["writeup_hidden"] is True and body["ai_rationale"] is None
    assert body["ai_score"] == 75 and body["score_report"]["band"] == "Shortlist"
    assert body["scorecard"]["rows"][0]["evidence"]
    assert (await detail(client, interview, admin))["ai_rationale"] == TEXT


@pytest.mark.asyncio
async def test_the_shared_link_gets_no_write_up_either(db_session, client):
    interview = await scored_with_text(db_session)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(display_url(interview.job), json={"show_writeup": False, "show_gaps": False}, headers=headers(admin))

    shared = await shared_detail_for(db_session, interview)

    assert shared.writeup_hidden is True and shared.gaps_hidden is True
    assert shared.ai_rationale is None
    assert shared.model_dump()["record"]["top_gaps"] == []

