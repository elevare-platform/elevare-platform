"""Weighing a job's scored interviews again under its current scoring profile
(docs/08_DECISIONS.md, item 63).

The ratings saved with each interview do not change and no model is called; the total, the band, the
key-competency flags and the lines of the written assessment that state them follow the profile."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.modules.interviews import service as service_module
from app.modules.interviews.band_recalculation import recalculate, retarget_text
from app.modules.interviews.models import (
    Interview,
    InterviewRescore,
    InterviewWeightedScore,
    JobScoringProfile,
)
from tests.conftest import make_employer

from .test_score_review import an_admin, detail, headers, review_url, scored_at

COLTON_BANDS = {"strong": 75, "shortlist": 60, "hold": 45}


def recalc_url(job):
    return f"/api/v1/interviews/jobs/{job.id}/recalculate-bands"


def competencies(strategy=60, pnl=40, *, key_strategy=True, key_pnl=False):
    return [
        {"name": "Strategy", "weight": strategy, "key": key_strategy},
        {"name": "P&L", "weight": pnl, "key": key_pnl},
    ]


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: fake)


async def with_profile(db_session, interview, *, comps=None, bands=None, key_min=3):
    db_session.add(
        JobScoringProfile(
            job_id=interview.job.id,
            competencies=comps or competencies(),
            bands=bands or dict(COLTON_BANDS),
            key_min_rating=key_min,
        )
    )
    await db_session.commit()


async def stored_report(db_session):
    return (await db_session.execute(select(InterviewWeightedScore))).scalar_one()


async def rated(db_session, interview, strategy, pnl, text=None):
    """Give the interview saved ratings (and the text that states them), on the default 60/40 weights."""
    row = await stored_report(db_session)
    rows = [
        {**row.report["rows"][0], "rating": strategy},
        {**row.report["rows"][1], "rating": pnl},
    ]
    row.report = {**row.report, "rows": rows, "practical": {"score": 3.8}, "record": {"gaps": ["Thin."]}}
    if text:
        interview.interview.ai_rationale = text
    await db_session.commit()


# ── The pure part ────────────────────────────────────────────────────────────────


def test_a_saved_report_is_weighed_again_with_the_new_weights_key_marks_and_cut_offs():
    old = {
        "rows": [
            {"name": "Strategy", "weight": 60, "key": True, "rating": 5, "rationale": "Strong."},
            {"name": "P&L", "weight": 40, "key": False, "rating": 2},
        ],
        "score": 76, "band": "Shortlist", "complete": True, "practical": {"score": 3.8},
    }

    new = recalculate(old, competencies(20, 80, key_strategy=False), COLTON_BANDS, 3)

    assert new["score"] == 52 and new["band"] == "Hold for evidence"
    assert [(r["weight"], r["key"], r["rating"]) for r in new["rows"]] == [(20, False, 5), (80, False, 2)]
    assert new["rows"][0]["rationale"] == "Strong."
    assert new["bands"] == COLTON_BANDS and new["practical"] == {"score": 3.8}


def test_a_competency_the_report_never_had_makes_the_score_incomplete_and_one_the_profile_dropped_goes():
    old = {"rows": [{"name": "Strategy", "weight": 100, "key": True, "rating": 4}, {"name": "Old", "weight": 0, "key": False, "rating": 3}]}

    new = recalculate(old, [{"name": "Strategy", "weight": 50, "key": True}, {"name": "Brand", "weight": 50, "key": False}], COLTON_BANDS, 3)

    assert [r["name"] for r in new["rows"]] == ["Strategy", "Brand"]
    assert new["rows"][1]["rating"] is None and new["rows"][1]["coverage"] == "NOT_ASSESSED"
    assert (new["complete"], new["score"], new["band"], new["unassessed"]) == (False, None, None, ["Brand"])


def test_a_report_with_no_rows_cannot_be_weighed():
    assert recalculate({"rows": []}, competencies(), COLTON_BANDS, 3) is None
    assert recalculate({}, competencies(), COLTON_BANDS, 3) is None


def test_the_written_assessment_lines_that_state_the_score_band_and_weights_are_brought_into_line():
    text = (
        "A steady candidate.\n\n"
        "Weighted score: 60 of 100. Suggested band (provisional): Do not shortlist.\n"
        "Key competency rated under 3 of 5: Strategy. The band is held at Hold for evidence until a person has looked at it.\n\n"
        "Competency scores (1 to 5):\n- Strategy (weight 60%, key): 3 of 5 (Competent). Fine.\n- P&L (weight 40%): 3 of 5 (Competent).\n\n"
        "Strengths:\n- Clear."
    )
    new = recalculate(
        {"rows": [{"name": "Strategy", "weight": 60, "key": True, "rating": 3}, {"name": "P&L", "weight": 40, "key": False, "rating": 3}]},
        competencies(30, 70, key_strategy=False), COLTON_BANDS, 3,
    )

    out = retarget_text(text, new)

    assert "Weighted score: 60 of 100. Suggested band (provisional): Shortlist." in out
    assert "Key competency rated under" not in out and "Do not shortlist" not in out
    assert "- Strategy (weight 30%): 3 of 5 (Competent). Fine." in out
    assert "- P&L (weight 70%): 3 of 5 (Competent)." in out
    assert "A steady candidate." in out and "Strengths:\n- Clear." in out and "\n\n\n" not in out


def test_an_incomplete_score_line_is_replaced_by_the_new_state():
    text = "Summary.\n\nINCOMPLETE SCORE: 60 of 60 weighted points could be assessed. A person decides.\n\nStrengths:\n- A."
    new = recalculate({"rows": [{"name": "Strategy", "weight": 100, "key": True, "rating": 4}]}, [{"name": "Strategy", "weight": 100, "key": True}], COLTON_BANDS, 3)

    out = retarget_text(text, new)

    assert "INCOMPLETE" not in out and "Weighted score: 80 of 100. Suggested band (provisional): Strong shortlist." in out


def test_a_text_without_those_lines_is_left_alone():
    assert retarget_text(None, {"rows": []}) is None
    assert retarget_text("Just a note.", recalculate({"rows": [{"name": "Strategy", "weight": 100, "key": True, "rating": 4}]}, [{"name": "Strategy", "weight": 100, "key": True}], COLTON_BANDS, 3)) == "Just a note."


# ── Through the API ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_new_cut_offs_move_the_band_without_touching_a_rating_or_a_model(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview)
    assert (await stored_report(db_session)).report["band"] == "Do not shortlist"

    resp = await client.post(recalc_url(interview.job), headers=headers(admin))

    assert resp.status_code == 200
    body = resp.json()
    assert (body["checked"], body["changed"], body["unchanged"], body["incomplete"], body["skipped"]) == (1, 1, 0, 0, 0)
    assert body["changes"][0]["from_band"] == "Do not shortlist" and body["changes"][0]["to_band"] == "Shortlist"
    shown = await detail(client, interview, interview.employer)
    assert shown["score_report"]["band"] == "Shortlist" and shown["ai_score"] == 60
    assert "Suggested band (provisional): Shortlist." in shown["ai_rationale"]
    assert [row["rating"] for row in shown["score_report"]["rows"]] == [3, 3]
    assert shown["score_report"]["bands"] == COLTON_BANDS


@pytest.mark.asyncio
async def test_new_weights_change_the_total_and_the_headings_and_the_record_and_practical_case_stay(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    text = "Weighted score: 76 of 100. Suggested band (provisional): Shortlist.\n\n- Strategy (weight 60%, key): 5 of 5 (Exceptional).\n- P&L (weight 40%): 2 of 5 (Limited)."
    await rated(db_session, interview, 5, 2, text)
    await with_profile(db_session, interview, comps=competencies(20, 80, key_strategy=False))

    await client.post(recalc_url(interview.job), headers=headers(admin))

    row = await stored_report(db_session)
    await db_session.refresh(interview.interview)
    assert row.report["score"] == 52 and interview.interview.ai_score == 52
    assert row.report["practical"] == {"score": 3.8} and row.report["record"] == {"gaps": ["Thin."]}
    assert interview.interview.ai_rationale.startswith("Weighted score: 52 of 100. Suggested band (provisional): Hold for evidence.")
    assert "- Strategy (weight 20%): 5 of 5" in interview.interview.ai_rationale
    assert "- P&L (weight 80%): 2 of 5" in interview.interview.ai_rationale


@pytest.mark.asyncio
async def test_the_key_competency_cap_follows_the_profile(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await rated(db_session, interview, 2, 5)  # the key competency is rated 2, under the minimum of 3
    await with_profile(db_session, interview, bands={"strong": 90, "shortlist": 50, "hold": 30})
    first = await client.post(recalc_url(interview.job), headers=headers(admin))
    capped = (await stored_report(db_session)).report
    assert first.status_code == 200
    assert capped["key_flags"] == ["Strategy"] and capped["band"] == "Hold for evidence"

    profile = (await db_session.execute(select(JobScoringProfile))).scalar_one()
    profile.competencies = competencies(key_strategy=False)
    await db_session.commit()
    await client.post(recalc_url(interview.job), headers=headers(admin))

    freed = (await stored_report(db_session)).report
    assert freed["key_flags"] == [] and freed["band"] == "Shortlist"


@pytest.mark.asyncio
async def test_a_profile_competency_the_interview_never_had_makes_it_incomplete_and_a_rescore_is_the_way_to_fill_it(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview, comps=competencies(50, 30) + [{"name": "Brand", "weight": 20, "key": False}])

    body = (await client.post(recalc_url(interview.job), headers=headers(admin))).json()

    assert (body["changed"], body["incomplete"]) == (1, 1)
    assert body["changes"][0]["to_score"] is None and body["changes"][0]["to_band"] is None
    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score is None


@pytest.mark.asyncio
async def test_running_it_twice_changes_nothing_the_second_time(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview)
    await client.post(recalc_url(interview.job), headers=headers(admin))

    again = (await client.post(recalc_url(interview.job), headers=headers(admin))).json()

    assert (again["checked"], again["changed"], again["unchanged"], again["changes"]) == (1, 0, 1, [])


@pytest.mark.asyncio
async def test_it_notes_what_the_band_and_score_were_before(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview)

    await client.post(recalc_url(interview.job), headers=headers(admin))

    note = (await stored_report(db_session)).report["recalculated"]
    assert (note["from_score"], note["from_band"], note["by"]) == (60, "Do not shortlist", str(admin.id))
    assert datetime.fromisoformat(note["at"]).tzinfo is not None


@pytest.mark.asyncio
async def test_an_admins_typed_total_stays_and_its_band_follows_the_new_cut_offs(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview)
    await client.put(review_url(interview), json={"score": 70}, headers=headers(admin))

    await client.post(recalc_url(interview.job), headers=headers(admin))

    shown = await detail(client, interview, interview.employer)
    assert shown["reviewed"] is True and shown["ai_score"] == 70
    assert shown["score_report"]["band"] == "Shortlist"


@pytest.mark.asyncio
async def test_an_interview_being_scored_again_right_now_is_skipped(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview)
    db_session.add(InterviewRescore(interview_id=interview.interview.id, status="PENDING", requested_at=datetime.now(UTC)))
    await db_session.commit()

    body = (await client.post(recalc_url(interview.job), headers=headers(admin))).json()

    assert (body["checked"], body["changed"], body["skipped"]) == (1, 0, 1)
    assert (await stored_report(db_session)).report["band"] == "Do not shortlist"


@pytest.mark.asyncio
async def test_only_scored_interviews_of_that_job_are_touched(client, db_session):
    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await with_profile(db_session, interview)
    stored = (await db_session.execute(select(Interview))).scalar_one()
    stored.status = "UPLOADED"
    await db_session.commit()

    body = (await client.post(recalc_url(interview.job), headers=headers(admin))).json()

    assert body["checked"] == 0 and body["changed"] == 0


@pytest.mark.asyncio
async def test_only_an_admin_can_do_it(client, db_session):
    interview = await scored_at(db_session, 60)
    teammate = make_employer(organization_id=interview.employer.organization_id)
    db_session.add(teammate)
    await with_profile(db_session, interview)

    for who in (headers(interview.employer), headers(teammate), {}):
        assert (await client.post(recalc_url(interview.job), headers=who)).status_code in (401, 403)
    assert (await stored_report(db_session)).report["band"] == "Do not shortlist"


@pytest.mark.asyncio
async def test_a_job_without_a_profile_or_an_unknown_job_is_refused(client, db_session):
    from uuid import uuid4

    interview = await scored_at(db_session, 60)
    admin = await an_admin(db_session)
    await db_session.commit()

    none = await client.post(recalc_url(interview.job), headers=headers(admin))
    missing = await client.post(f"/api/v1/interviews/jobs/{uuid4()}/recalculate-bands", headers=headers(admin))

    assert (none.status_code, none.json()["code"]) == (422, "NO_SCORING_PROFILE")
    assert missing.status_code == 404
