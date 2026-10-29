"""An Elevare admin scores an already scored interview again (docs/08_DECISIONS.md, item 58).

The interview stays scored while it runs, so a failure can never mark it FAILED or give credits back.
The new system result replaces the old one, the admin's earlier edits and the system's earlier score
stay in the review history, nobody is charged and the employer is not told."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from sqlalchemy import select

from app.modules.ai.schema import InterviewScoringResult
from app.modules.interviews import service as service_module
from app.modules.interviews import tasks as interviews_tasks
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import InterviewScoreReview, InterviewWeightedScore
from app.modules.notifications.models import Notification
from tests.conftest import make_employer

from .test_interview_tasks import _patch_engine_to_use_test_session
from .test_score_review import an_admin, detail, headers, scored_at

pytestmark = pytest.mark.asyncio


def rescore_url(interview):
    return f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/rescore?job_id={interview.job.id}"


def review_url(interview):
    return f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/score-review?job_id={interview.job.id}"


@pytest.fixture
def queued(monkeypatch):
    task = MagicMock()
    monkeypatch.setattr(service_module, "rescore_interview_task", task)
    return task.delay


def scorer(monkeypatch, result=None, side_effect=None):
    instance = MagicMock()
    instance.score_interview_transcript = AsyncMock(return_value=result, side_effect=side_effect)
    instance._client.close = AsyncMock()
    monkeypatch.setattr(interviews_tasks, "AnthropicCVExtractionService", Mock(return_value=instance))
    monkeypatch.setattr(interviews_tasks, "_scoring_profile_for", AsyncMock(return_value=(None, None)))
    return instance


# ── The request ──────────────────────────────────────────────────────────────────


async def test_an_admin_queues_a_rescore_of_a_scored_interview(client, db_session, queued):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.post(rescore_url(interview), headers=headers(admin))

    assert resp.status_code == 202 and resp.json() == {"queued": True}
    queued.assert_called_once()
    assert queued.call_args.args[0] == str(interview.interview.id)
    assert queued.call_args.args[1] == str(admin.id)


async def test_nobody_but_an_admin_can_ask_for_a_rescore(client, db_session, queued):
    interview = await scored_at(db_session, 58)
    teammate = make_employer(organization_id=interview.employer.organization_id)
    db_session.add(teammate)
    await db_session.commit()

    for who in (headers(interview.employer), headers(teammate), {}):
        assert (await client.post(rescore_url(interview), headers=who)).status_code in (401, 403)
    queued.assert_not_called()


async def test_only_a_scored_interview_with_a_transcript_can_be_scored_again(client, db_session, queued):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    interview.interview.status = InterviewStatus.UPLOADED.value
    await db_session.commit()

    not_scored = await client.post(rescore_url(interview), headers=headers(admin))
    interview.interview.status = InterviewStatus.SCORED.value
    interview.interview.transcript = None
    await db_session.commit()
    no_transcript = await client.post(rescore_url(interview), headers=headers(admin))

    assert (not_scored.status_code, not_scored.json()["code"]) == (422, "INTERVIEW_NOT_SCORED")
    assert (no_transcript.status_code, no_transcript.json()["code"]) == (422, "INTERVIEW_NO_TRANSCRIPT")
    queued.assert_not_called()


async def test_an_unknown_job_or_interview_is_not_found(client, db_session, queued):
    from uuid import uuid4

    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    no_job = await client.post(
        f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/rescore?job_id={uuid4()}", headers=headers(admin)
    )
    no_interview = await client.post(
        f"/api/v1/interviews/{uuid4()}/rescore?job_id={interview.job.id}", headers=headers(admin)
    )

    assert no_job.status_code == 404 and no_interview.status_code == 404
    queued.assert_not_called()


# ── The task ─────────────────────────────────────────────────────────────────────


async def test_the_new_result_replaces_the_old_and_the_admins_edits_go_but_stay_in_the_history(
    client, db_session, monkeypatch
):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"score": 89, "reason": "Calibrated."}, headers=headers(admin))
    assert (await detail(client, interview, interview.employer))["ai_score"] == 89
    scorer(monkeypatch, InterviewScoringResult(score=71, summary="A fair showing.", strengths=["Clear"]))

    done = await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    assert done is True
    shown = await detail(client, interview, interview.employer)
    assert shown["ai_score"] == 71 and shown["reviewed"] is False
    assert "A fair showing." in shown["ai_rationale"]
    rows = (
        await db_session.execute(
            select(InterviewScoreReview).order_by(InterviewScoreReview.reviewed_at, InterviewScoreReview.created_at)
        )
    ).scalars().all()
    assert len(rows) == 2 and rows[0].score == 89
    marker = rows[-1]
    assert (marker.score, marker.ratings, marker.rationale, marker.scorecard) == (None, None, None, None)
    assert (marker.original_score, marker.reviewed_by, marker.reviewed_by_name) == (58, admin.id, "Ada Admin")
    assert "earlier result was 58" in marker.reason
    history = (await detail(client, interview, admin))["score_review"]["reviews"]
    assert len(history) == 2 and history[0]["reason"].startswith("Scored again by the system")
    assert history[1]["score"] == 89 and history[1]["reason"] == "Calibrated."


async def test_the_interview_stays_scored_nobody_is_charged_and_the_employer_is_not_told(db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    scorer(monkeypatch, InterviewScoringResult(score=71, summary="Fair."))
    refund = AsyncMock()
    monkeypatch.setattr(interviews_tasks, "refund_interview_credits", refund)

    await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    await db_session.refresh(interview.interview)
    assert interview.interview.status == InterviewStatus.SCORED.value and interview.interview.ai_score == 71
    refund.assert_not_called()
    assert (await db_session.execute(select(Notification))).scalars().first() is None


async def test_a_rescore_with_no_edits_still_records_the_earlier_system_result(db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    scorer(monkeypatch, InterviewScoringResult(score=64, summary="Fair."))

    await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    row = (await db_session.execute(select(InterviewScoreReview))).scalar_one()
    assert (row.original_score, row.original_band, row.score) == (58, "Do not shortlist", None)


async def test_the_weighted_report_is_replaced_not_added_to(db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    scorer(monkeypatch, InterviewScoringResult(score=64, summary="Fair.", strengths=["Clear route to market."]))

    await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    reports = (await db_session.execute(select(InterviewWeightedScore))).scalars().all()
    assert len(reports) == 1 and reports[0].report["record"]["strengths"] == ["Clear route to market."]


async def test_a_failed_call_changes_nothing_and_leaves_the_edits_in_force(client, db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))
    scorer(monkeypatch, InterviewScoringResult(failed=True))

    done = await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    assert done is False
    shown = await detail(client, interview, interview.employer)
    assert shown["ai_score"] == 89 and shown["reviewed"] is True
    await db_session.refresh(interview.interview)
    assert interview.interview.ai_score == 58 and interview.interview.status == InterviewStatus.SCORED.value
    assert len((await db_session.execute(select(InterviewScoreReview))).scalars().all()) == 1


async def test_an_error_leaves_the_interview_scored_not_failed_and_no_credits_returned(db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()
    scorer(monkeypatch, side_effect=RuntimeError("model down"))
    refund = AsyncMock()
    monkeypatch.setattr(interviews_tasks, "refund_interview_credits", refund)
    updates = []
    real_update = interviews_tasks.InterviewRepository.update

    async def spy(self, interview_id, data):
        updates.append(data)
        return await real_update(self, interview_id, data)

    monkeypatch.setattr(interviews_tasks.InterviewRepository, "update", spy)

    with pytest.raises(RuntimeError):
        await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    # Nothing was written (the interview is never marked FAILED), and no credits came back.
    assert updates == []
    refund.assert_not_called()


async def test_an_interview_that_is_not_scored_is_left_alone(db_session, monkeypatch):
    _patch_engine_to_use_test_session(monkeypatch, db_session)
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    interview.interview.status = InterviewStatus.UPLOADED.value
    await db_session.commit()
    instance = scorer(monkeypatch, InterviewScoringResult(score=71))

    done = await interviews_tasks._rescore_interview_async(interview.interview.id, admin.id, "Ada Admin")

    assert done is False
    instance.score_interview_transcript.assert_not_called()
