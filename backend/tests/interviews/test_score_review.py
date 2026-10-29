"""A reviewed interview score (docs/08_DECISIONS.md, item 52).

An Elevare admin can set the score of a finished interview in place of the one the system worked
out. The band follows the score by the job's own cut-offs, the employer's screen and the shared
link both show it with a "reviewed" flag, the system's own score and band are kept for the admin,
and nobody else can do it."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews import service as service_module
from app.modules.interviews.assessment_text import weighted_lines
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import InterviewScoreReview, InterviewWeightedScore
from app.modules.interviews.score_review import apply_review
from app.modules.interviews.service import InterviewService
from tests.conftest import make_admin, make_employer

from .test_strict_interview import make_strict

BANDS = {"strong": 85, "shortlist": 75, "hold": 65}


def report_for(score, *, key_flags=()):
    """The weighted report as scoring stores it, with its total and the band that total gives."""
    band = (
        "Strong shortlist" if score >= 85 else "Shortlist" if score >= 75 else "Hold for evidence" if score >= 65 else "Do not shortlist"
    )
    return {
        "rows": [
            {"name": "Strategy", "weight": 60, "key": True, "rating": 3},
            {"name": "P&L", "weight": 40, "key": False, "rating": 3},
        ],
        "points": float(score),
        "assessed_weight": 100,
        "total_weight": 100,
        "complete": True,
        "score": score,
        "band": band,
        "bands": BANDS,
        "key_min_rating": 3,
        "key_flags": list(key_flags),
        "unassessed": [],
    }


def headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/v")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: fake)


async def scored_at(db_session, score=58, *, owner=None, key_flags=()):
    """A finished strict interview scored ``score`` with a weighted report, whose written assessment
    carries the score and band lines."""
    interview = await make_strict(db_session, status=InterviewStatus.SCORED.value, transcript="AI: q\n\nCandidate: a")
    report = report_for(score, key_flags=key_flags)
    row = interview.interview
    row.completed_at = datetime.now(UTC)
    row.ai_score = score
    row.ai_scored_at = datetime.now(UTC)
    row.ai_rationale = "A steady candidate.\n\n" + "\n".join(weighted_lines(report)) + "\n\nStrengths:\n- Clear"
    db_session.add(InterviewWeightedScore(interview_id=row.id, report=report))
    if owner is not None:
        interview.job.employer_id = owner.id
    await db_session.commit()
    return interview


def review_url(interview):
    return f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/score-review?job_id={interview.job.id}"


async def detail(client, interview, user):
    response = await client.get(
        "/api/v1/interviews/detail",
        params={"job_id": str(interview.job.id), "talent_pool_profile_id": str(interview.interview.talent_pool_profile_id)},
        headers=headers(user),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def an_admin(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    return admin


# ── The rule ─────────────────────────────────────────────────────────────────────


def test_a_reviewed_score_sets_the_band_by_the_jobs_own_cut_offs():
    for score, band in [(89, "Strong shortlist"), (80, "Shortlist"), (70, "Hold for evidence"), (40, "Do not shortlist")]:
        shown = apply_review(score=58, rationale=None, report=report_for(58), review_score=score)
        assert (shown.score, shown.report["band"], shown.reviewed) == (score, band, True)


def test_a_cut_off_is_the_score_that_reaches_it():
    assert apply_review(score=1, rationale=None, report=report_for(1), review_score=85).report["band"] == "Strong shortlist"
    assert apply_review(score=1, rationale=None, report=report_for(1), review_score=84).report["band"] == "Shortlist"


def test_a_low_key_competency_no_longer_holds_the_band_once_a_person_has_set_the_score():
    report = with_ratings(strategy=2)  # the key competency is rated under the minimum of 3
    assert report["key_flags"] == []  # (the fixture's own flags are not used: they are recomputed)
    shown = apply_review(score=52, rationale=None, report=report, review_score=90)
    assert shown.report["band"] == "Strong shortlist" and shown.report["key_flags"] == ["Strategy"]


def test_no_review_leaves_the_systems_result_untouched():
    original = report_for(58)
    shown = apply_review(score=58, rationale="text", report=original, review_score=None)
    assert (shown.score, shown.rationale, shown.report, shown.reviewed) == (58, "text", original, False)


def test_a_job_without_a_scoring_profile_changes_the_score_only():
    shown = apply_review(score=40, rationale="text", report=None, review_score=75)
    assert (shown.score, shown.report, shown.reviewed) == (75, None, True)


def test_a_reviewed_score_completes_an_incomplete_one():
    incomplete = {**report_for(0), "complete": False, "score": None, "band": None, "unassessed": ["P&L"]}
    shown = apply_review(score=None, rationale=None, report=incomplete, review_score=72)
    assert (shown.report["complete"], shown.report["unassessed"], shown.report["band"]) == (True, [], "Hold for evidence")


def test_the_written_assessment_agrees_with_the_reviewed_numbers():
    original = report_for(58)
    text = "Summary.\n\n" + "\n".join(weighted_lines(original)) + "\n\nStrengths:\n- Clear"

    shown = apply_review(score=58, rationale=text, report=original, review_score=89)

    assert "Weighted score: 89 of 100. Suggested band (provisional): Strong shortlist." in shown.rationale
    assert "58" not in shown.rationale and "Do not shortlist" not in shown.rationale
    assert shown.rationale.startswith("Summary.") and shown.rationale.endswith("- Clear")


# ── Who may ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_admin_sets_the_score_for_any_job_and_the_band_follows(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))

    assert resp.status_code == 200
    assert resp.json() == {"score": 89, "band": "Strong shortlist", "reviewed": True}


@pytest.mark.asyncio
async def test_nobody_but_an_admin_can_set_or_remove_a_score(client, db_session):
    from .test_interview_router import register_and_promote

    interview = await scored_at(db_session, 58)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.commit()
    token, _ = await register_and_promote(client, db_session, "CANDIDATE")

    for who in (headers(interview.employer), headers(stranger), {"Authorization": f"Bearer {token}"}, {}):
        put = await client.put(review_url(interview), json={"score": 89}, headers=who)
        delete = await client.delete(review_url(interview), headers=who)
        assert put.status_code in (401, 403) and delete.status_code in (401, 403)

    assert (await db_session.execute(select(InterviewScoreReview))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_score_outside_0_to_100_is_refused(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    for bad in (-1, 101, "high"):
        assert (await client.put(review_url(interview), json={"score": bad}, headers=headers(admin))).status_code == 422
    assert (await client.put(review_url(interview), json={"score": 0}, headers=headers(admin))).status_code == 200
    assert (await client.put(review_url(interview), json={"score": 100}, headers=headers(admin))).status_code == 200


@pytest.mark.asyncio
async def test_only_a_scored_interview_can_be_reviewed(client, db_session):
    interview = await scored_at(db_session, 58)
    interview.interview.status = InterviewStatus.UPLOADED.value
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_NOT_SCORED"


@pytest.mark.asyncio
async def test_an_unknown_interview_or_job_is_not_found(client, db_session):
    from uuid import uuid4

    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    wrong_job = await client.put(
        f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/score-review?job_id={uuid4()}",
        json={"score": 89},
        headers=headers(admin),
    )
    wrong_person = await client.put(
        f"/api/v1/interviews/{uuid4()}/score-review?job_id={interview.job.id}", json={"score": 89}, headers=headers(admin)
    )

    assert wrong_job.status_code == 404 and wrong_person.status_code == 404


# ── What is shown, and to whom ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_employer_sees_the_reviewed_score_and_band_flagged_but_not_who_or_the_original(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"score": 89, "reason": "Strong on the panel's read."}, headers=headers(admin))

    body = await detail(client, interview, interview.employer)

    assert body["ai_score"] == 89 and body["reviewed"] is True
    assert body["score_report"]["score"] == 89 and body["score_report"]["band"] == "Strong shortlist"
    assert body["score_report"]["reviewed"] is True
    assert "Weighted score: 89 of 100. Suggested band (provisional): Strong shortlist." in body["ai_rationale"]
    assert body["score_review"] is None
    for hidden in ("58", "Do not shortlist", "Strong on the panel", admin.first_name):
        assert hidden not in str(body["score_review"])
    assert "Do not shortlist" not in body["ai_rationale"]


@pytest.mark.asyncio
async def test_the_shared_link_shows_the_same_reviewed_result(db_session):
    from app.modules.jobs.repository import JobRepository

    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    job_id, profile_id = interview.job.id, interview.interview.talent_pool_profile_id
    service = InterviewService(db_session)
    try:
        await service.review_score(admin, job_id, profile_id, 89, None)
        job = await JobRepository(db_session).get_by_id(job_id)
        row = await service._repo.get_by_job_and_profile(job_id, profile_id)
        shared = await service.build_detail(job, row, include_panel_decision=False)
    finally:
        await service.close()

    assert shared.ai_score == 89 and shared.reviewed is True
    assert shared.score_report.band == "Strong shortlist" and shared.score_report.reviewed is True
    assert shared.score_review is None
    assert "Do not shortlist" not in shared.ai_rationale


@pytest.mark.asyncio
async def test_an_admin_alone_sees_the_original_the_history_and_who(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    interview.job.employer_id = admin.id  # an admin can open the detail of a job they manage
    await db_session.commit()
    await client.put(review_url(interview), json={"score": 89, "reason": "Rated on the panel's read."}, headers=headers(admin))

    body = await detail(client, interview, admin)

    history = body["score_review"]
    assert (history["original_score"], history["original_band"]) == (58, "Do not shortlist")
    [only] = history["reviews"]
    assert (only["score"], only["reason"], only["reviewed_by_name"]) == (89, "Rated on the panel's read.", f"{admin.first_name} {admin.last_name}")


@pytest.mark.asyncio
async def test_each_change_is_kept_with_the_systems_own_score_and_band(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))
    await client.put(review_url(interview), json={"score": 70, "reason": "  Second   look  "}, headers=headers(admin))

    rows = (
        await db_session.execute(select(InterviewScoreReview).order_by(InterviewScoreReview.reviewed_at))
    ).scalars().all()
    assert [(r.score, r.reason, r.original_score, r.original_band) for r in rows] == [
        (89, None, 58, "Do not shortlist"),
        (70, "Second look", 58, "Do not shortlist"),
    ]
    assert (await detail(client, interview, interview.employer))["ai_score"] == 70


@pytest.mark.asyncio
async def test_removing_a_review_brings_the_systems_result_back_and_keeps_the_history(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))

    removed = await client.delete(review_url(interview), headers=headers(admin))

    assert removed.json() == {"score": 58, "band": "Do not shortlist", "reviewed": False}
    body = await detail(client, interview, interview.employer)
    assert (body["ai_score"], body["reviewed"], body["score_report"]["band"]) == (58, False, "Do not shortlist")
    assert len((await db_session.execute(select(InterviewScoreReview))).scalars().all()) == 2


@pytest.mark.asyncio
async def test_an_interview_nobody_reviewed_is_shown_exactly_as_the_system_scored_it(client, db_session):
    interview = await scored_at(db_session, 58)

    body = await detail(client, interview, interview.employer)

    assert (body["ai_score"], body["reviewed"], body["score_report"]["band"]) == (58, False, "Do not shortlist")
    assert "Do not shortlist" in body["ai_rationale"]
    assert body["score_report"].get("reviewed") is False


@pytest.mark.asyncio
async def test_the_stored_score_is_never_overwritten(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))

    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 58
    report = (await db_session.execute(select(InterviewWeightedScore.report))).scalar_one()
    assert report["score"] == 58 and report["band"] == "Do not shortlist"


# ── Competency ratings ───────────────────────────────────────────────────────────
# report_for(): Strategy (weight 60, key) and P&L (weight 40), both rated 3, so the system's total
# is 60 * 3/5 + 40 * 3/5 = 60.


def with_ratings(**ratings):
    """The weighted report of two competencies rated as given (both 3 unless said), whose total and
    band are the system's own for those ratings."""
    strategy, pnl = ratings.get("strategy", 3), ratings.get("pnl", 3)
    score = round(strategy / 5 * 60 + pnl / 5 * 40)
    report = report_for(score)
    report["rows"] = [
        {"name": "Strategy", "weight": 60, "key": True, "rating": strategy, "coverage": "FULLY_ASSESSED"},
        {"name": "P&L", "weight": 40, "key": False, "rating": pnl, "coverage": "FULLY_ASSESSED"},
    ]
    return report


def text_for(report):
    lines = [
        f"- Strategy (weight 60%, key): {report['rows'][0]['rating']} of 5.",
        f"- P&L (weight 40%): {report['rows'][1]['rating']} of 5.",
    ]
    return "Summary.\n\n" + "\n".join(weighted_lines(report)) + "\n\nCompetency scores (1 to 5):\n" + "\n".join(lines)


def test_changing_a_rating_works_the_total_out_from_all_the_ratings_and_the_band_follows():
    report = with_ratings()  # 60

    shown = apply_review(score=60, rationale=None, report=report, review_score=None, review_ratings={"Strategy": 5})

    assert shown.score == 84  # 60 * 5/5 + 40 * 3/5
    assert shown.report["band"] == "Shortlist" and shown.report["reviewed"] is True and shown.report["complete"] is True
    assert [row["rating"] for row in shown.report["rows"]] == [5, 3]


def test_a_typed_total_wins_over_the_total_the_ratings_give():
    shown = apply_review(score=60, rationale=None, report=with_ratings(), review_score=95, review_ratings={"Strategy": 4})

    assert shown.score == 95 and shown.report["band"] == "Strong shortlist"
    assert [row["rating"] for row in shown.report["rows"]] == [4, 3]


def test_rating_names_are_matched_without_regard_to_case_and_unknown_or_bad_ones_change_nothing():
    shown = apply_review(score=60, rationale=None, report=with_ratings(), review_score=None, review_ratings={"strategy": 5, "Nope": 5, "P&L": 9})

    assert [row["rating"] for row in shown.report["rows"]] == [5, 3]


def test_the_key_competency_note_follows_the_reviewed_ratings_and_never_caps_the_band():
    shown = apply_review(score=60, rationale=None, report=with_ratings(), review_score=None, review_ratings={"Strategy": 2, "P&L": 5})

    assert shown.report["key_flags"] == ["Strategy"]
    assert shown.score == round(2 / 5 * 60 + 5 / 5 * 40) == 64
    assert shown.report["band"] == "Do not shortlist"  # 64 is under the Hold cut-off of 65


def test_rating_a_competency_that_was_not_assessed_completes_the_score():
    report = with_ratings()
    report.update(complete=False, score=None, band=None, unassessed=["P&L"])
    report["rows"][1]["rating"] = None

    shown = apply_review(score=None, rationale=None, report=report, review_score=None, review_ratings={"P&L": 4})

    assert (shown.report["complete"], shown.report["unassessed"], shown.score) == (True, [], round(3 / 5 * 60 + 4 / 5 * 40))


def test_changing_a_rating_while_another_is_still_unrated_leaves_the_score_incomplete():
    report = with_ratings()
    report.update(complete=False, score=None, band=None, unassessed=["P&L"])
    report["rows"][1]["rating"] = None

    shown = apply_review(score=None, rationale=None, report=report, review_score=None, review_ratings={"Strategy": 5})

    assert (shown.score, shown.report["complete"], shown.report["band"], shown.reviewed) == (None, False, None, True)
    assert shown.report["unassessed"] == ["P&L"]


def test_the_written_assessment_shows_the_changed_ratings_and_the_new_total_and_keeps_the_rest():
    report = with_ratings()
    text = (
        "Summary.\n\n" + "\n".join(weighted_lines(report)) + "\n\nCompetency scores (1 to 5):\n"
        "- Strategy (weight 60%, key): 3 of 5 (Competent).\nThin on scale.\n"
        "- P&L (weight 40%): 3 of 5 (Competent).\nSolid.\n\nStrengths:\n- Clear"
    )

    shown = apply_review(score=60, rationale=text, report=report, review_score=None, review_ratings={"Strategy": 5})

    assert "- Strategy (weight 60%, key): 5 of 5 (Exceptional)." in shown.rationale
    assert "- P&L (weight 40%): 3 of 5 (Competent)." in shown.rationale
    assert "Weighted score: 84 of 100. Suggested band (provisional): Shortlist." in shown.rationale
    assert "Thin on scale." in shown.rationale and shown.rationale.endswith("- Clear")
    assert "3 of 5 (Competent).\nThin" not in shown.rationale


def test_ratings_alone_change_nothing_for_a_job_without_a_scoring_profile():
    shown = apply_review(score=70, rationale="text", report=None, review_score=None, review_ratings={"Strategy": 5})

    assert (shown.score, shown.reviewed) == (70, False)


@pytest.mark.asyncio
async def test_an_admin_changes_ratings_and_the_total_follows(client, db_session):
    interview = await scored_at(db_session, 60)
    report = with_ratings()
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = report
    interview.interview.ai_score = 60
    interview.interview.ai_rationale = text_for(report)
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.put(review_url(interview), json={"ratings": {"strategy": 5}}, headers=headers(admin))

    assert resp.status_code == 200
    assert resp.json() == {"score": 84, "band": "Shortlist", "reviewed": True}
    body = await detail(client, interview, interview.employer)
    assert body["ai_score"] == 84 and body["reviewed"] is True
    assert [r["rating"] for r in body["score_report"]["rows"]] == [5, 3]
    assert "Weighted score: 84 of 100" in body["ai_rationale"]
    saved = (await db_session.execute(select(InterviewScoreReview))).scalar_one()
    assert saved.ratings == {"Strategy": 5} and saved.score is None


@pytest.mark.asyncio
async def test_ratings_can_be_sent_with_a_typed_total_and_the_total_wins(client, db_session):
    interview = await scored_at(db_session, 60)
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = with_ratings()
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.put(review_url(interview), json={"ratings": {"Strategy": 4}, "score": 95}, headers=headers(admin))

    assert resp.json() == {"score": 95, "band": "Strong shortlist", "reviewed": True}


@pytest.mark.asyncio
async def test_only_the_ratings_that_differ_from_the_systems_are_kept(client, db_session):
    interview = await scored_at(db_session, 60)
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = with_ratings()
    admin = await an_admin(db_session)
    await db_session.commit()

    await client.put(review_url(interview), json={"ratings": {"Strategy": 3, "P&L": 5}}, headers=headers(admin))

    saved = (await db_session.execute(select(InterviewScoreReview))).scalar_one()
    assert saved.ratings == {"P&L": 5}


@pytest.mark.asyncio
async def test_bad_ratings_are_refused_and_nothing_is_saved(client, db_session):
    interview = await scored_at(db_session, 60)
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = with_ratings()
    admin = await an_admin(db_session)
    await db_session.commit()

    unknown = await client.put(review_url(interview), json={"ratings": {"Leadership": 4}}, headers=headers(admin))
    too_high = await client.put(review_url(interview), json={"ratings": {"Strategy": 6}}, headers=headers(admin))
    too_low = await client.put(review_url(interview), json={"ratings": {"Strategy": 0}}, headers=headers(admin))
    not_a_number = await client.put(review_url(interview), json={"ratings": {"Strategy": "five"}}, headers=headers(admin))
    same = await client.put(review_url(interview), json={"ratings": {"Strategy": 3}}, headers=headers(admin))
    nothing = await client.put(review_url(interview), json={}, headers=headers(admin))

    assert unknown.json()["code"] == "UNKNOWN_COMPETENCY"
    assert too_high.json()["code"] == "INVALID_RATING" and too_low.json()["code"] == "INVALID_RATING"
    assert not_a_number.status_code == 422
    assert same.json()["code"] == "NOTHING_TO_REVIEW" and nothing.json()["code"] == "NOTHING_TO_REVIEW"
    assert (await db_session.execute(select(InterviewScoreReview))).scalars().all() == []


@pytest.mark.asyncio
async def test_ratings_cannot_be_changed_on_an_interview_without_competencies(client, db_session):
    interview = await make_strict(db_session, status=InterviewStatus.SCORED.value, transcript="x")
    interview.interview.ai_score = 70
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.put(review_url(interview), json={"ratings": {"Strategy": 5}}, headers=headers(admin))
    typed = await client.put(review_url(interview), json={"score": 80}, headers=headers(admin))

    assert resp.json()["code"] == "NO_COMPETENCIES"
    assert typed.json() == {"score": 80, "band": None, "reviewed": True}


@pytest.mark.asyncio
async def test_the_latest_review_replaces_the_earlier_one_whole_and_removing_it_restores_the_ratings(client, db_session):
    interview = await scored_at(db_session, 60)
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = with_ratings()
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"ratings": {"Strategy": 5}}, headers=headers(admin))

    await client.put(review_url(interview), json={"ratings": {"P&L": 5}}, headers=headers(admin))
    second = await detail(client, interview, interview.employer)
    await client.delete(review_url(interview), headers=headers(admin))
    restored = await detail(client, interview, interview.employer)

    assert [r["rating"] for r in second["score_report"]["rows"]] == [3, 5]  # Strategy is the system's again
    assert [r["rating"] for r in restored["score_report"]["rows"]] == [3, 3]
    assert (restored["ai_score"], restored["reviewed"]) == (60, False)
    assert len((await db_session.execute(select(InterviewScoreReview))).scalars().all()) == 3


@pytest.mark.asyncio
async def test_the_admin_sees_the_systems_ratings_and_the_ratings_of_each_review(client, db_session):
    interview = await scored_at(db_session, 60)
    row = (await db_session.execute(select(InterviewWeightedScore))).scalar_one()
    row.report = with_ratings()
    admin = await an_admin(db_session)
    interview.job.employer_id = admin.id
    await db_session.commit()
    await client.put(review_url(interview), json={"ratings": {"Strategy": 5}, "reason": "Seen the plan."}, headers=headers(admin))

    history = (await detail(client, interview, admin))["score_review"]

    assert history["original_ratings"] == {"Strategy": 3, "P&L": 3}
    assert history["reviews"][0]["ratings"] == {"Strategy": 5}
    assert history["reviews"][0]["score"] is None
