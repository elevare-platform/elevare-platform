"""Recovering a strict interview that failed before it was finished.

Seen on the first real use: candidates answered every question, the recording never reached
storage, and two hours later the stale sweep marked the interview FAILED. From then on the link,
the retry and a resend all refused it, and the dashboard said "Scoring failed" although nothing
was ever scored. The employer can now complete it (the recording was there after all), reopen it
(the candidate sends the recording their browser kept) or start it over, and the sweep leaves an
interview that reached the upload step alone for longer."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select, update

from app.core.exceptions import InsufficientCreditsException
from app.modules.interviews import service as service_module
from app.modules.interviews.enums import STALE_UPLOAD_TIMEOUT, InterviewStatus
from app.modules.interviews.models import (
    Interview,
    InterviewConductEvent,
    InterviewPanelDecision,
    InterviewTurn,
    InterviewWeightedScore,
)
from app.modules.interviews.repository import InterviewRepository
from app.modules.talent_pool.models import TalentPoolProfiles
from tests.conftest import make_employer, make_organization_for

from .test_strict_conduct import _headers, events_of, run_of, started, stop
from .test_strict_interview import _base, answer, start

ONE_QUESTION = [("Tell us about a system you designed.", 120)]


def _recover_url(interview, *, start_over=False):
    return (
        f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/recover"
        f"?job_id={interview.job.id}" + ("&start_over=true" if start_over else "")
    )


@pytest.fixture
def invite_email(monkeypatch):
    task = MagicMock()
    monkeypatch.setattr(service_module, "send_ai_interview_invite_email", task)
    return task


@pytest.fixture
def storage(monkeypatch):
    """Storage that holds nothing, and a scoring task that records it was queued."""
    storage = MagicMock()
    storage.get_object_size = AsyncMock(return_value=0)
    storage.delete_file = AsyncMock()
    monkeypatch.setattr(service_module, "get_storage_service", lambda: storage)
    scoring = MagicMock()
    monkeypatch.setattr(service_module, "transcribe_and_score_interview_task", scoring)
    return MagicMock(storage=storage, scoring=scoring)


async def failed_interview(client, db_session, clock, *, questions=None, answers=1, email=True):
    """A strict interview, started and answered, whose upload address was issued, left idle until
    the sweep marked it FAILED."""
    interview, first = await started(client, db_session, questions=questions)
    state = first
    for _ in range(answers):
        state = (await answer(client, interview.token, state["turn"]["id"])).json()
        if state["turn"] is None:
            break
    row = interview.interview
    row.r2_key = f"interviews/{row.id}/recording.webm"
    row.status = InterviewStatus.FAILED.value
    if email:
        profile = (
            await db_session.execute(
                select(TalentPoolProfiles).where(TalentPoolProfiles.id == row.talent_pool_profile_id)
            )
        ).scalar_one()
        profile.override_email = "candidate@example.com"
    await db_session.commit()
    clock.advance(3 * 3600)
    return interview, state


async def refreshed(db_session, interview):
    await db_session.refresh(interview.interview)
    return interview.interview


# ---------------------------------------------------------------------------
# Reopening: the candidate sends the recording their browser kept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reopening_lets_the_candidate_open_the_link_again_and_finish(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, state = await failed_interview(client, db_session, clock, questions=ONE_QUESTION)
    assert state["finished"] is True

    resp = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "reopened" and body["status"] == "PENDING"
    assert body["email_sent"] is True
    assert body["interview_url"].endswith(f"/interview/{interview.token}")
    invite_email.delay.assert_called_once()
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.PENDING.value
    # The recording that never arrived is forgotten, so no clip points at a file that is not there.
    assert row.r2_key is None
    # The candidate opens the link: the interview is finished, with its answers, and not ended.
    clock.advance(600)
    resumed = (await start(client, interview.token, accepted=False)).json()
    assert resumed["ended"] is None and resumed["finished"] is True
    # And the recording can now be uploaded and the interview completed.
    storage.storage.generate_presigned_upload_url = AsyncMock(return_value="https://r2.test/up")
    storage.storage.get_object_size = AsyncMock(return_value=4096)
    assert (await client.post(f"{_base(interview.token)}/upload-url")).status_code == 201
    done = await client.post(f"{_base(interview.token)}/complete", json={})
    assert done.status_code == 200
    assert (await refreshed(db_session, interview)).status == InterviewStatus.UPLOADED.value
    storage.scoring.delay.assert_called_once()


@pytest.mark.asyncio
async def test_reopening_gives_back_the_time_left_when_they_dropped_not_the_hours_since(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock, answers=0)

    await client.post(_recover_url(interview), headers=_headers(interview.employer))
    clock.advance(600)
    state = (await start(client, interview.token, accepted=False)).json()

    # The first question, with the whole of its allowance, and the whole interview's time.
    assert state["ended"] is None and state["turn"]["number"] == 1
    assert state["turn"]["seconds_left"] == state["turn"]["time_limit_seconds"]
    assert state["seconds_left_total"] > 0


@pytest.mark.asyncio
async def test_reopening_the_first_visit_back_is_not_counted_as_a_reload(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock)
    await client.post(_recover_url(interview), headers=_headers(interview.employer))

    state = (await start(client, interview.token, accepted=False)).json()

    assert state["ended"] is None and state["leaves"] == 0
    assert await events_of(db_session, interview.interview, "RELOAD") == []


@pytest.mark.asyncio
async def test_reopening_keeps_the_answers(client, db_session, fakes, clock, storage, invite_email):
    interview, _ = await failed_interview(client, db_session, clock, answers=2)

    await client.post(_recover_url(interview), headers=_headers(interview.employer))

    turns = (
        await db_session.execute(
            select(InterviewTurn).where(InterviewTurn.interview_id == interview.interview.id)
        )
    ).scalars().all()
    assert len([turn for turn in turns if turn.answer_text]) == 2


@pytest.mark.asyncio
async def test_reopening_without_an_email_on_file_still_returns_the_link(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock, email=False)

    resp = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert resp.json()["email_sent"] is False and resp.json()["interview_url"]
    invite_email.delay.assert_not_called()


# ---------------------------------------------------------------------------
# The recording was in storage after all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_recording_found_in_storage_completes_the_interview_and_queues_scoring(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock, questions=ONE_QUESTION)
    storage.storage.get_object_size = AsyncMock(return_value=8192)

    resp = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "completed" and resp.json()["status"] == "UPLOADED"
    assert resp.json()["interview_url"] is None and resp.json()["email_sent"] is False
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.UPLOADED.value and row.completed_at is not None
    assert row.r2_key and row.transcript
    storage.scoring.delay.assert_called_once_with(str(row.id))
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_starting_over_never_trusts_the_old_recording(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock)
    storage.storage.get_object_size = AsyncMock(return_value=8192)

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.json()["outcome"] == "started_over"
    storage.scoring.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Starting over
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_starting_over_gives_a_fresh_interview_with_a_new_clock(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock, answers=2)

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "started_over" and resp.json()["email_sent"] is True
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.PENDING.value
    assert row.r2_key is None and row.started_at is None and row.transcript is None
    run = await run_of(db_session, interview.interview)
    assert run.started_at is None and run.questions is None and run.attempt == 1
    turns = (
        await db_session.execute(
            select(InterviewTurn).where(InterviewTurn.interview_id == row.id)
        )
    ).scalars().all()
    events = (
        await db_session.execute(
            select(InterviewConductEvent).where(InterviewConductEvent.interview_id == row.id)
        )
    ).scalars().all()
    assert turns == [] and events == []

    # The candidate has to accept the rules again, and gets question 1 with the whole clock.
    refused = await start(client, interview.token, accepted=False)
    assert refused.status_code == 422 and refused.json()["code"] == "INTERVIEW_RULES_NOT_ACCEPTED"
    fresh = (await start(client, interview.token)).json()
    assert fresh["turn"]["number"] == 1
    assert fresh["turn"]["seconds_left"] == fresh["turn"]["time_limit_seconds"]
    assert fresh["seconds_left_total"] == 20 * 60


# ---------------------------------------------------------------------------
# Who may, and when
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_only_an_interview_that_failed_before_finishing_can_be_recovered(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await started(client, db_session)
    in_progress = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    row = interview.interview
    row.status = InterviewStatus.FAILED.value
    row.completed_at = datetime.now(UTC)  # it was completed: scoring is what failed
    await db_session.commit()
    scoring_failed = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    for resp in (in_progress, scoring_failed):
        assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_NOT_RECOVERABLE"


@pytest.mark.asyncio
async def test_an_interview_cannot_be_recovered_twice(client, db_session, fakes, clock, storage, invite_email):
    interview, _ = await failed_interview(client, db_session, clock)
    await client.post(_recover_url(interview), headers=_headers(interview.employer))

    again = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert again.status_code == 422 and again.json()["code"] == "INTERVIEW_NOT_RECOVERABLE"


@pytest.mark.asyncio
async def test_a_live_interview_is_not_recovered_this_way(client, db_session, fakes, clock, storage, invite_email):
    from .test_strict_interview import make_strict

    interview = await make_strict(db_session, strict=False)
    interview.interview.status = InterviewStatus.FAILED.value
    await db_session.commit()

    resp = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_NOT_RECOVERABLE"


@pytest.mark.asyncio
async def test_a_teammate_may_recover_but_a_stranger_and_a_candidate_may_not(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    from .test_interview_router import register_and_promote

    # The interview was charged when it was invited; the test builds it without that charge.
    monkeypatch.setattr(service_module.InterviewService, "_charge_for_invite", AsyncMock())
    interview, _ = await failed_interview(client, db_session, clock)
    organization = await make_organization_for(db_session, interview.employer, company_name="Acme")
    teammate = make_employer(organization_id=organization.id)
    stranger = make_employer()
    db_session.add_all([teammate, stranger])
    await db_session.commit()
    token, _user = await register_and_promote(client, db_session, "CANDIDATE")

    by_stranger = await client.post(_recover_url(interview), headers=_headers(stranger))
    by_candidate = await client.post(_recover_url(interview), headers={"Authorization": f"Bearer {token}"})
    by_teammate = await client.post(_recover_url(interview), headers=_headers(teammate))

    assert by_stranger.status_code == 403 and by_candidate.status_code == 403
    assert by_teammate.status_code == 200


@pytest.mark.asyncio
async def test_recovering_takes_the_payment_that_a_resend_would(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    interview, _ = await failed_interview(client, db_session, clock)
    charge = AsyncMock()
    monkeypatch.setattr(service_module.InterviewService, "_charge_for_invite", charge)

    await client.post(_recover_url(interview), headers=_headers(interview.employer))

    charge.assert_awaited_once()


@pytest.mark.asyncio
async def test_short_of_credits_changes_nothing(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    interview, _ = await failed_interview(client, db_session, clock)
    monkeypatch.setattr(
        service_module.InterviewService,
        "_charge_for_invite",
        AsyncMock(side_effect=InsufficientCreditsException("Not enough credits")),
    )

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 402
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.FAILED.value
    turns = (await db_session.execute(select(InterviewTurn).where(InterviewTurn.interview_id == row.id))).scalars().all()
    assert turns  # nothing was deleted
    invite_email.delay.assert_not_called()


# ---------------------------------------------------------------------------
# The dashboard says why
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_interview_list_says_whether_the_recording_never_arrived_or_scoring_failed(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await failed_interview(client, db_session, clock)
    url = f"/api/v1/interview-list?job_id={interview.job.id}"

    never = (await client.get(url, headers=_headers(interview.employer))).json()["items"][0]
    interview.interview.completed_at = datetime.now(UTC)
    await db_session.commit()
    scoring = (await client.get(url, headers=_headers(interview.employer))).json()["items"][0]
    interview.interview.status = InterviewStatus.SCORED.value
    await db_session.commit()
    fine = (await client.get(url, headers=_headers(interview.employer))).json()["items"][0]

    assert (never["interview_status"], never["interview_failure"]) == ("FAILED", "NEVER_FINISHED")
    assert (scoring["interview_status"], scoring["interview_failure"]) == ("FAILED", "SCORING_FAILED")
    assert fine["interview_failure"] is None


# ---------------------------------------------------------------------------
# The stale sweep leaves an interview that reached the upload step alone for longer
# ---------------------------------------------------------------------------


async def _idle_since(db_session, interview, hours, *, with_key):
    row = interview.interview
    await db_session.execute(
        update(Interview)
        .where(Interview.id == row.id)
        .values(
            status=InterviewStatus.IN_PROGRESS.value,
            r2_key=f"interviews/{row.id}/recording.webm" if with_key else None,
            updated_at=datetime.now(UTC) - timedelta(hours=hours),
        )
    )
    await db_session.commit()


async def _stale(db_session):
    now = datetime.now(UTC)
    from app.modules.interviews.enums import STALE_INTERVIEW_TIMEOUT

    return await InterviewRepository(db_session).get_stale_in_progress_interviews(
        now - STALE_INTERVIEW_TIMEOUT, upload_before=now - STALE_UPLOAD_TIMEOUT
    )


@pytest.mark.asyncio
async def test_an_interview_without_a_recording_step_is_stale_after_two_hours(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await _idle_since(db_session, interview, 3, with_key=False)

    assert [row.id for row in await _stale(db_session)] == [interview.interview.id]


@pytest.mark.asyncio
async def test_an_interview_waiting_for_its_recording_is_not_stale_after_two_hours(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await _idle_since(db_session, interview, 3, with_key=True)

    assert await _stale(db_session) == []


@pytest.mark.asyncio
async def test_an_interview_waiting_for_its_recording_is_stale_after_three_days(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await _idle_since(db_session, interview, 24 * 3 + 1, with_key=True)

    assert [row.id for row in await _stale(db_session)] == [interview.interview.id]


# ---------------------------------------------------------------------------
# An interview that ended early can be started over (a retake)
# ---------------------------------------------------------------------------


async def ended_with_an_empty_recording(client, db_session, clock, *, email=True):
    """A strict interview the candidate stopped, whose recording arrived with nothing in it: the
    employer sees "Review and reinstate", no video, and the answers."""
    interview, first = await started(client, db_session)
    await answer(client, interview.token, first["turn"]["id"])
    await stop(client, interview.token)
    row = interview.interview
    await db_session.refresh(row)
    row.r2_key = f"interviews/{row.id}/recording.webm"
    row.completed_at = datetime.now(UTC)
    if email:
        profile = (
            await db_session.execute(
                select(TalentPoolProfiles).where(TalentPoolProfiles.id == row.talent_pool_profile_id)
            )
        ).scalar_one()
        profile.override_email = "candidate@example.com"
    await db_session.commit()
    clock.advance(3600)
    return interview


@pytest.mark.asyncio
async def test_an_interview_that_ended_early_can_be_started_over_for_a_retake(
    client, db_session, fakes, clock, storage, invite_email
):
    interview = await ended_with_an_empty_recording(client, db_session, clock)
    old_key = (await refreshed(db_session, interview)).r2_key

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "started_over" and resp.json()["email_sent"] is True
    invite_email.delay.assert_called_once()
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.PENDING.value
    assert row.r2_key is None and row.completed_at is None and row.transcript is None
    assert row.video_expires_at is None
    # The old recording is removed from storage.
    storage.storage.delete_file.assert_awaited_once_with(old_key)
    # The candidate takes it from the top, with the rules and the whole clock.
    fresh = (await start(client, interview.token)).json()
    assert fresh["ended"] is None and fresh["turn"]["number"] == 1
    assert fresh["seconds_left_total"] == 20 * 60


@pytest.mark.asyncio
async def test_a_retake_discards_the_attempts_answers_and_timeline(client, db_session, fakes, clock, storage, invite_email):
    interview = await ended_with_an_empty_recording(client, db_session, clock)

    await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    turns = (
        await db_session.execute(select(InterviewTurn).where(InterviewTurn.interview_id == interview.interview.id))
    ).scalars().all()
    assert turns == [] and await events_of(db_session, interview.interview) == []


@pytest.mark.asyncio
async def test_an_interview_that_ended_early_is_reinstated_not_reopened(
    client, db_session, fakes, clock, storage, invite_email
):
    interview = await ended_with_an_empty_recording(client, db_session, clock)

    resp = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_NOT_RECOVERABLE"
    assert "Reinstate" in resp.json()["message"]
    assert (await refreshed(db_session, interview)).status == InterviewStatus.STOPPED.value
    storage.storage.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_interview_the_candidate_is_in_the_middle_of_cannot_be_started_over(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await started(client, db_session)

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_CANDIDATE_ACTIVE"
    assert "try again in about" in resp.json()["message"]
    assert (await refreshed(db_session, interview)).status == InterviewStatus.IN_PROGRESS.value
    storage.storage.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_candidate_who_answered_a_moment_ago_is_not_thrown_away(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, state = await started(client, db_session)
    await answer(client, interview.token, state["turn"]["id"])
    clock.advance(3 * 60)

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_CANDIDATE_ACTIVE"
    assert (await refreshed(db_session, interview)).status == InterviewStatus.IN_PROGRESS.value
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_a_stuck_in_progress_interview_is_started_over_on_a_new_link(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, state = await started(client, db_session)
    await answer(client, interview.token, state["turn"]["id"])
    old_token = interview.token
    profile = (
        await db_session.execute(
            select(TalentPoolProfiles).where(TalentPoolProfiles.id == interview.interview.talent_pool_profile_id)
        )
    ).scalar_one()
    profile.override_email = "candidate@example.com"
    await db_session.commit()
    clock.advance(11 * 60)

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    body = resp.json()
    assert body["outcome"] == "started_over" and body["status"] == "PENDING" and body["email_sent"] is True
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.PENDING.value and row.started_at is None
    # A new link: the old one does not lead into the fresh attempt any more.
    assert row.token != old_token
    assert body["interview_url"].endswith(f"/interview/{row.token}")
    assert invite_email.delay.call_args.kwargs["interview_url"].endswith(f"/interview/{row.token}")
    assert (await start(client, old_token)).status_code != 200
    # The answers of the stuck attempt are gone, and the fresh one begins with the whole clock.
    turns = (
        await db_session.execute(select(InterviewTurn).where(InterviewTurn.interview_id == row.id))
    ).scalars().all()
    assert turns == []
    fresh = (await start(client, row.token)).json()
    assert fresh["turn"]["number"] == 1 and fresh["seconds_left_total"] == 20 * 60


@pytest.mark.asyncio
async def test_starting_over_a_stuck_interview_does_not_charge_again(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    interview, _ = await started(client, db_session)
    clock.advance(11 * 60)
    charge = AsyncMock()
    monkeypatch.setattr(service_module.InterviewService, "_charge_for_invite", charge)

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    charge.assert_awaited_once()
    assert charge.await_args.kwargs.get("again") is False


@pytest.mark.asyncio
async def test_a_stranger_cannot_start_over_somebody_elses_stuck_interview(
    client, db_session, fakes, clock, storage, invite_email
):
    interview, _ = await started(client, db_session)
    clock.advance(11 * 60)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.commit()

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(stranger))

    assert resp.status_code in (403, 404)
    assert (await refreshed(db_session, interview)).status == InterviewStatus.IN_PROGRESS.value


@pytest.mark.asyncio
async def test_a_file_that_cannot_be_deleted_never_undoes_the_retake(client, db_session, fakes, clock, storage, invite_email):
    interview = await ended_with_an_empty_recording(client, db_session, clock)
    storage.storage.delete_file = AsyncMock(side_effect=RuntimeError("storage is down"))

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200 and resp.json()["outcome"] == "started_over"
    assert (await refreshed(db_session, interview)).status == InterviewStatus.PENDING.value


# ---------------------------------------------------------------------------
# A COMPLETED interview can be taken again (the employer's retake)
# ---------------------------------------------------------------------------


async def scored_interview(client, db_session, clock, *, score=38):
    """A strict interview that was finished and scored low, with a weighted report, a recording
    and a panel decision, which the employer now wants the candidate to take again."""
    interview, first = await started(client, db_session)
    await answer(client, interview.token, first["turn"]["id"])
    row = interview.interview
    await db_session.refresh(row)
    row.status = InterviewStatus.SCORED.value
    row.completed_at = datetime.now(UTC)
    row.r2_key = f"interviews/{row.id}/recording.webm"
    row.ai_score = score
    row.ai_rationale = "Thin answers."
    row.ai_scored_at = datetime.now(UTC)
    row.transcript = "AI: q\n\nCandidate: a"
    db_session.add(InterviewWeightedScore(interview_id=row.id, report={"score": score, "complete": True}))
    db_session.add(
        InterviewPanelDecision(
            interview_id=row.id,
            decision="DO_NOT_SHORTLIST",
            rationale="Too thin for the role.",
            decided_by=interview.employer.id,
            decided_by_name="Panel Member",
            decided_at=datetime.now(UTC),
        )
    )
    profile = (
        await db_session.execute(
            select(TalentPoolProfiles).where(TalentPoolProfiles.id == row.talent_pool_profile_id)
        )
    ).scalar_one()
    profile.override_email = "candidate@example.com"
    await db_session.commit()
    clock.advance(3600)
    return interview


@pytest.mark.asyncio
async def test_a_scored_interview_can_be_taken_again_and_the_first_result_is_replaced(
    client, db_session, fakes, clock, storage, invite_email
):
    interview = await scored_interview(client, db_session, clock)
    old_key = (await refreshed(db_session, interview)).r2_key
    interview_id = interview.interview.id

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert resp.json()["outcome"] == "started_over" and resp.json()["email_sent"] is True
    invite_email.delay.assert_called_once()
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.PENDING.value
    # The first score, its written assessment and its report are gone, with the answers and recording.
    assert (row.ai_score, row.ai_rationale, row.ai_scored_at) == (None, None, None)
    assert row.completed_at is None and row.transcript is None and row.r2_key is None
    reports = (await db_session.execute(select(InterviewWeightedScore).where(InterviewWeightedScore.interview_id == interview_id))).scalars().all()
    turns = (await db_session.execute(select(InterviewTurn).where(InterviewTurn.interview_id == interview_id))).scalars().all()
    assert reports == [] and turns == []
    storage.storage.delete_file.assert_awaited_once_with(old_key)
    # The hiring panel's earlier decision is kept (an append-only record); it carries its date.
    decisions = (await db_session.execute(select(InterviewPanelDecision).where(InterviewPanelDecision.interview_id == interview_id))).scalars().all()
    assert [d.decision for d in decisions] == ["DO_NOT_SHORTLIST"]
    # The candidate takes it from the top with a full clock.
    fresh = (await start(client, interview.token)).json()
    assert fresh["turn"]["number"] == 1 and fresh["seconds_left_total"] == 20 * 60


@pytest.mark.asyncio
async def test_a_retake_also_clears_an_elevare_reviewers_score(
    client, db_session, fakes, clock, storage, invite_email
):
    from app.modules.interviews.models import InterviewScoreReview

    interview = await scored_interview(client, db_session, clock)
    db_session.add(
        InterviewScoreReview(
            interview_id=interview.interview.id,
            score=89,
            reviewed_by_name="Admin",
            reviewed_at=datetime.now(UTC),
            original_score=38,
        )
    )
    await db_session.commit()

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert (await db_session.execute(select(InterviewScoreReview))).scalars().all() == []


@pytest.mark.asyncio
async def test_a_scored_interview_is_not_reopened_or_reinstated_only_started_over(
    client, db_session, fakes, clock, storage, invite_email
):
    interview = await scored_interview(client, db_session, clock)

    resp = await client.post(_recover_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_NOT_RECOVERABLE"
    assert "start it over" in resp.json()["message"]
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.SCORED.value and row.ai_score == 38
    storage.storage.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_an_interview_being_scored_right_now_cannot_be_taken_again(
    client, db_session, fakes, clock, storage, invite_email
):
    interview = await scored_interview(client, db_session, clock)
    interview.interview.status = InterviewStatus.UPLOADED.value
    await db_session.commit()

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_PROCESSING"
    assert (await refreshed(db_session, interview)).ai_score == 38


@pytest.mark.asyncio
async def test_an_interview_whose_scoring_failed_can_be_taken_again(
    client, db_session, fakes, clock, storage, invite_email
):
    interview = await scored_interview(client, db_session, clock)
    interview.interview.status = InterviewStatus.FAILED.value
    interview.interview.ai_score = None
    await db_session.commit()

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200 and resp.json()["outcome"] == "started_over"
    assert (await refreshed(db_session, interview)).status == InterviewStatus.PENDING.value


async def _paid_organization(db_session, interview, *, balance=100, cost=10):
    """The job's owner gets an organization with credits, and the interview was charged at invite."""
    from app.modules.credits.service import CreditsService

    organization = await make_organization_for(db_session, interview.employer, company_name="Acme")
    credits = CreditsService(db_session)
    await credits.grant(organization.id, balance)
    await credits.charge_interview(organization.id, interview.interview.id, cost)
    await db_session.commit()
    return organization, credits


@pytest.mark.asyncio
async def test_a_retake_takes_the_interviews_credits_again(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    monkeypatch.setattr(service_module.settings, "interview_credit_cost", 10)
    interview = await scored_interview(client, db_session, clock)
    organization, credits = await _paid_organization(db_session, interview)
    assert await credits.get_balance(organization.id) == 90

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert await credits.get_balance(organization.id) == 80


@pytest.mark.asyncio
async def test_pressing_retake_twice_takes_the_credits_once(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    monkeypatch.setattr(service_module.settings, "interview_credit_cost", 10)
    interview = await scored_interview(client, db_session, clock)
    organization, credits = await _paid_organization(db_session, interview)

    first = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))
    second = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert first.status_code == 200
    # The second finds an interview that is already pending, which is not recoverable.
    assert second.status_code == 422 and second.json()["code"] == "INTERVIEW_NOT_RECOVERABLE"
    assert await credits.get_balance(organization.id) == 80


@pytest.mark.asyncio
async def test_a_retake_with_too_few_credits_changes_nothing(
    client, db_session, fakes, clock, storage, invite_email, monkeypatch
):
    monkeypatch.setattr(service_module.settings, "interview_credit_cost", 10)
    interview = await scored_interview(client, db_session, clock)
    organization, credits = await _paid_organization(db_session, interview, balance=15)  # 5 left

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(interview.employer))

    assert resp.status_code == 402
    row = await refreshed(db_session, interview)
    assert row.status == InterviewStatus.SCORED.value and row.ai_score == 38 and row.r2_key
    turns = (await db_session.execute(select(InterviewTurn).where(InterviewTurn.interview_id == row.id))).scalars().all()
    assert turns
    assert await credits.get_balance(organization.id) == 5
    invite_email.delay.assert_not_called()
    storage.storage.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_stranger_cannot_make_a_candidate_retake(client, db_session, fakes, clock, storage, invite_email):
    interview = await scored_interview(client, db_session, clock)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.commit()

    resp = await client.post(_recover_url(interview, start_over=True), headers=_headers(stranger))

    assert resp.status_code == 403
    assert (await refreshed(db_session, interview)).ai_score == 38
