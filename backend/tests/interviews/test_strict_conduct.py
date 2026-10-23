"""Leaving the screen, warnings, ending, stopping and reinstating a strict interview.

The rules (docs/08_DECISIONS.md, "The new strict, text-only AI interview", item 25): the 1st to
3rd leave warns, the 4th ends the interview, and so does 60 seconds away in total; the server
times every leave with its own clock; a reload is a leave; key presses are recorded and never
count; "I need to stop" ends it as the candidate's own choice; either ending keeps the
recording and the answers; the employer who owns the job can reinstate it and the candidate
carries on where they stopped, with the time they had left."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import ValidationException
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interviews import service as service_module
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import (
    Interview,
    InterviewConductEvent,
    InterviewTranscriptCheck,
    StrictInterviewRun,
)
from app.modules.interviews.recording_merge import final_key
from app.modules.notifications.models import Notification
from app.modules.talent_pool.models import TalentPoolProfiles
from tests.conftest import make_employer, make_organization_for

from .conftest import LONG_ANSWER
from .test_strict_interview import _base, answer, make_strict, start


async def event(client, token, type, **body):
    return await client.post(f"{_base(token)}/strict/event", json={"type": type, **body})


async def stop(client, token):
    return await client.post(f"{_base(token)}/strict/stop")


async def leave_and_return(client, clock, token, seconds, cause="HIDDEN"):
    await event(client, token, "left", cause=cause)
    clock.advance(seconds)
    return await event(client, token, "returned")


async def run_of(db_session, interview):
    result = await db_session.execute(
        select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview.id)
    )
    run = result.scalar_one()
    await db_session.refresh(run)
    return run


async def events_of(db_session, interview, kind=None):
    query = select(InterviewConductEvent).where(InterviewConductEvent.interview_id == interview.id)
    if kind:
        query = query.where(InterviewConductEvent.kind == kind)
    result = await db_session.execute(query.order_by(InterviewConductEvent.occurred_at))
    return list(result.scalars().all())


async def status_of(db_session, interview):
    await db_session.refresh(interview)
    return interview.status


async def started(client, db_session, *, questions=None):
    """A strict interview, started, with the clock at its start."""
    interview = await make_strict(db_session) if questions is None else await make_strict(db_session, questions=questions)
    first = (await start(client, interview.token)).json()
    return interview, first


# ---------------------------------------------------------------------------
# Leaving
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_leave_is_counted_and_timed_by_the_server(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    clock.advance(30)

    await event(client, interview.token, "left", cause="BLUR")
    clock.advance(12)
    state = (await event(client, interview.token, "returned")).json()

    assert state["leaves"] == 1 and state["ended"] is None
    assert state["away_seconds"] == 12
    [leave] = await events_of(db_session, interview.interview, "LEFT_PAGE")
    assert (leave.detail, leave.duration_seconds, leave.counted) == ("BLUR", 12.0, True)
    assert leave.occurred_at == clock.now() - timedelta(seconds=12)


@pytest.mark.asyncio
async def test_the_browser_cannot_shorten_a_leave_the_server_timed(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await event(client, interview.token, "left", cause="HIDDEN")
    clock.advance(20)

    # The body carries no duration at all, and whatever else is sent is ignored.
    resp = await client.post(
        f"{_base(interview.token)}/strict/event",
        json={"type": "returned", "duration_seconds": 0.1},
    )

    assert resp.json()["away_seconds"] == 20


@pytest.mark.asyncio
async def test_saying_it_has_left_twice_is_one_leave(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    await event(client, interview.token, "left", cause="HIDDEN")
    clock.advance(5)
    state = (await event(client, interview.token, "left", cause="BLUR")).json()

    assert state["leaves"] == 1
    assert len(await events_of(db_session, interview.interview, "LEFT_PAGE")) == 1


@pytest.mark.asyncio
async def test_saying_it_is_back_when_it_never_left_changes_nothing(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    state = (await event(client, interview.token, "returned")).json()

    assert state["leaves"] == 0 and state["away_seconds"] == 0
    assert await events_of(db_session, interview.interview, "LEFT_PAGE") == []


@pytest.mark.asyncio
async def test_the_first_three_leaves_only_warn(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    states = [(await leave_and_return(client, clock, interview.token, 5)).json() for _ in range(3)]

    assert [state["leaves"] for state in states] == [1, 2, 3]
    assert all(state["ended"] is None for state in states)
    assert await status_of(db_session, interview.interview) == InterviewStatus.IN_PROGRESS.value
    assert states[-1]["max_leaves"] == 4 and states[-1]["max_away_seconds"] == 60


@pytest.mark.asyncio
async def test_the_fourth_leave_ends_the_interview_at_once(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    for _ in range(3):
        await leave_and_return(client, clock, interview.token, 5)

    state = (await event(client, interview.token, "left", cause="HIDDEN")).json()

    assert state["ended"] == "TOO_MANY_LEAVES"
    assert await status_of(db_session, interview.interview) == InterviewStatus.ENDED_CONDUCT.value
    run = await run_of(db_session, interview.interview)
    assert run.end_reason == "TOO_MANY_LEAVES" and run.ended_at == clock.now()


@pytest.mark.asyncio
async def test_sixty_seconds_away_in_total_ends_the_interview_when_the_last_leave_is_over(
    client, db_session, fakes, clock
):
    interview, _ = await started(client, db_session)
    await leave_and_return(client, clock, interview.token, 25)
    await leave_and_return(client, clock, interview.token, 25)

    state = (await leave_and_return(client, clock, interview.token, 15)).json()

    assert state["leaves"] == 3
    assert state["ended"] == "TOO_LONG_AWAY"
    assert await status_of(db_session, interview.interview) == InterviewStatus.ENDED_CONDUCT.value


@pytest.mark.asyncio
async def test_a_total_just_under_sixty_seconds_does_not_end_it(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await leave_and_return(client, clock, interview.token, 20)
    await leave_and_return(client, clock, interview.token, 20)

    state = (await leave_and_return(client, clock, interview.token, 19)).json()

    assert state["ended"] is None and state["away_seconds"] == 59


@pytest.mark.asyncio
async def test_a_leave_that_is_still_open_counts_towards_the_sixty_seconds_on_the_next_contact(
    client, db_session, fakes, clock
):
    interview, _ = await started(client, db_session)
    await event(client, interview.token, "left", cause="HIDDEN")
    clock.advance(61)

    state = (await event(client, interview.token, "ping")).json()

    assert state["ended"] == "TOO_LONG_AWAY"


@pytest.mark.asyncio
async def test_closing_the_tab_does_not_stop_the_clock(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await event(client, interview.token, "left", cause="HIDDEN")
    clock.advance(75)  # the tab was closed, and the link is opened again 75 seconds later

    state = (await start(client, interview.token, accepted=False)).json()

    assert state["ended"] == "TOO_LONG_AWAY"
    assert state["turn"] is None
    [leave] = await events_of(db_session, interview.interview, "LEFT_PAGE")
    assert leave.duration_seconds == 75.0
    # The open leave was closed, not turned into a second one.
    assert await events_of(db_session, interview.interview, "RELOAD") == []


@pytest.mark.asyncio
async def test_a_heartbeat_changes_nothing_but_when_the_screen_was_last_heard_from(
    client, db_session, fakes, clock
):
    interview, _ = await started(client, db_session)
    clock.advance(15)

    state = (await event(client, interview.token, "ping")).json()

    assert state["leaves"] == 0 and state["ended"] is None
    run = await run_of(db_session, interview.interview)
    assert run.last_seen_at == clock.now()
    assert await events_of(db_session, interview.interview) == []


# ---------------------------------------------------------------------------
# Key presses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_key_press_is_recorded_and_never_counts_towards_ending(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    for _ in range(30):
        clock.advance(1)
        state = (await event(client, interview.token, "key", key="Escape")).json()

    assert state["leaves"] == 0 and state["ended"] is None
    assert state["key_presses"] == 30 and state["away_seconds"] == 0
    assert await status_of(db_session, interview.interview) == InterviewStatus.IN_PROGRESS.value
    keys = await events_of(db_session, interview.interview, "KEY_PRESS")
    assert len(keys) == 30 and all(key.counted is False and key.detail == "Escape" for key in keys)


@pytest.mark.asyncio
async def test_an_odd_key_name_is_stored_as_other(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    await event(client, interview.token, "key", key="<script>alert(1)</script>")
    await event(client, interview.token, "key", key="Ctrl+T")

    details = [key.detail for key in await events_of(db_session, interview.interview, "KEY_PRESS")]
    assert details == ["Other", "Ctrl+T"]


@pytest.mark.asyncio
async def test_the_full_key_combination_is_stored_not_just_the_first_key(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    for combination in ("Ctrl+Shift+I", "Alt+Tab", "Ctrl+Alt+Shift+Meta+Backspace", "Meta+L"):
        await event(client, interview.token, "key", key=combination)

    details = [key.detail for key in await events_of(db_session, interview.interview, "KEY_PRESS")]
    assert details == ["Ctrl+Shift+I", "Alt+Tab", "Ctrl+Alt+Shift+Meta+Backspace", "Meta+L"]


@pytest.mark.asyncio
async def test_a_key_name_longer_than_the_column_is_refused_not_cut_short(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    resp = await event(client, interview.token, "key", key="Ctrl+" * 9)

    assert resp.status_code == 422
    assert await events_of(db_session, interview.interview, "KEY_PRESS") == []


@pytest.mark.asyncio
async def test_the_number_of_stored_key_presses_is_capped(client, db_session, fakes, clock, monkeypatch):
    from app.modules.interviews import strict_conduct

    monkeypatch.setattr(strict_conduct, "MAX_KEY_EVENTS", 3)
    interview, _ = await started(client, db_session)

    for _ in range(6):
        await event(client, interview.token, "key", key="F12")

    assert len(await events_of(db_session, interview.interview, "KEY_PRESS")) == 3


@pytest.mark.asyncio
async def test_something_the_interview_does_not_record_is_refused(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    resp = await client.post(f"{_base(interview.token)}/strict/event", json={"type": "explode"})

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_nothing_can_be_reported_before_the_interview_starts(client, db_session, fakes, clock):
    interview = await make_strict(db_session)

    resp = await event(client, interview.token, "left", cause="HIDDEN")

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# A reload is a leave
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_reload_is_one_leave_timed_from_when_the_screen_was_last_heard_from(
    client, db_session, fakes, clock
):
    interview, _ = await started(client, db_session)
    clock.advance(10)
    await event(client, interview.token, "ping")
    clock.advance(20)

    state = (await start(client, interview.token, accepted=False)).json()

    assert state["leaves"] == 1 and state["away_seconds"] == 20 and state["ended"] is None
    [reload] = await events_of(db_session, interview.interview, "RELOAD")
    assert (reload.counted, reload.duration_seconds) == (True, 20.0)


@pytest.mark.asyncio
async def test_a_request_repeated_a_moment_later_is_not_a_reload(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    clock.advance(1)

    state = (await start(client, interview.token, accepted=False)).json()

    assert state["leaves"] == 0
    assert await events_of(db_session, interview.interview, "RELOAD") == []


@pytest.mark.asyncio
async def test_the_fourth_reload_ends_the_interview(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    for _ in range(3):
        clock.advance(5)
        state = (await start(client, interview.token, accepted=False)).json()
        assert state["ended"] is None

    clock.advance(5)
    state = (await start(client, interview.token, accepted=False)).json()

    assert state["leaves"] == 4 and state["ended"] == "TOO_MANY_LEAVES"


@pytest.mark.asyncio
async def test_a_reload_after_a_long_gap_ends_it_because_of_the_time_away(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    clock.advance(90)

    state = (await start(client, interview.token, accepted=False)).json()

    assert state["ended"] == "TOO_LONG_AWAY"


@pytest.mark.asyncio
async def test_reloads_and_leaves_add_up_to_the_same_four(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await leave_and_return(client, clock, interview.token, 5)
    await leave_and_return(client, clock, interview.token, 5)
    clock.advance(5)
    await start(client, interview.token, accepted=False)

    state = (await event(client, interview.token, "left", cause="BLUR")).json()

    assert state["leaves"] == 4 and state["ended"] == "TOO_MANY_LEAVES"


# ---------------------------------------------------------------------------
# After it ended
# ---------------------------------------------------------------------------


async def ended_interview(client, db_session, clock):
    interview, _ = await started(client, db_session)
    for _ in range(3):
        await leave_and_return(client, clock, interview.token, 5)
    await event(client, interview.token, "left", cause="HIDDEN")
    return interview


@pytest.mark.asyncio
async def test_an_ended_interview_shows_no_question_and_says_why(client, db_session, fakes, clock):
    interview = await ended_interview(client, db_session, clock)

    resp = await start(client, interview.token, accepted=False)

    assert resp.status_code == 200
    body = resp.json()
    assert body["ended"] == "TOO_MANY_LEAVES"
    assert body["turn"] is None and body["finished"] is False


@pytest.mark.asyncio
async def test_nothing_more_is_recorded_once_it_has_ended(client, db_session, fakes, clock):
    interview = await ended_interview(client, db_session, clock)
    before = len(await events_of(db_session, interview.interview))

    for kind in ("ping", "returned", "key"):
        state = (await event(client, interview.token, kind, key="Escape")).json()
        assert state["ended"] == "TOO_MANY_LEAVES"

    assert len(await events_of(db_session, interview.interview)) == before


@pytest.mark.asyncio
async def test_an_answer_that_arrives_after_it_ended_is_dropped_and_the_screen_is_told(
    client, db_session, fakes, clock
):
    interview, first = await started(client, db_session)
    for _ in range(3):
        await leave_and_return(client, clock, interview.token, 5)
    await event(client, interview.token, "left", cause="HIDDEN")

    state = (await answer(client, interview.token, first["turn"]["id"])).json()

    assert state["ended"] == "TOO_MANY_LEAVES"
    assert fakes.speech.calls == 1  # transcribed before the lock; the answer is not saved
    from .test_strict_interview import turns_of

    assert (await turns_of(db_session, interview.interview))[0].answered_at is None


@pytest.mark.asyncio
async def test_the_ending_is_in_the_timeline_with_its_reason(client, db_session, fakes, clock):
    interview = await ended_interview(client, db_session, clock)

    [ending] = await events_of(db_session, interview.interview, "ENDED")

    assert ending.detail == "TOO_MANY_LEAVES" and ending.occurred_at == clock.now()


@pytest.mark.asyncio
async def test_the_employer_who_created_the_job_is_told_in_the_app(client, db_session, fakes, clock):
    interview = await ended_interview(client, db_session, clock)

    notifications = (
        await db_session.execute(
            select(Notification).where(
                Notification.recipient_id == interview.job.employer_id,
                Notification.type == "AI_INTERVIEW_ENDED",
            )
        )
    ).scalars().all()

    assert len(notifications) == 1
    note = notifications[0]
    assert note.entity_type == "JOB" and note.entity_id == interview.job.id
    assert "ended early" in note.title and "not proof" in note.body
    assert note.context == {
        "job_id": str(interview.job.id),
        "talent_pool_profile_id": str(interview.interview.talent_pool_profile_id),
    }


# ---------------------------------------------------------------------------
# "I need to stop"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stopping_ends_it_as_the_candidates_own_choice_not_as_conduct(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    clock.advance(40)

    state = (await stop(client, interview.token)).json()

    assert state["ended"] == "STOPPED" and state["turn"] is None
    assert await status_of(db_session, interview.interview) == InterviewStatus.STOPPED.value
    [stopped] = await events_of(db_session, interview.interview, "STOPPED")
    assert stopped.detail == "STOPPED"
    assert await events_of(db_session, interview.interview, "ENDED") == []
    # It does not count as a leave.
    assert state["leaves"] == 0


@pytest.mark.asyncio
async def test_stopping_tells_the_employer_the_candidate_chose_to(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)

    await stop(client, interview.token)

    note = (
        await db_session.execute(
            select(Notification).where(
                Notification.type == "AI_INTERVIEW_ENDED",
                Notification.recipient_id == interview.job.employer_id,
            )
        )
    ).scalar_one()
    assert "stopped their AI interview" in note.title and "chose to stop" in note.body


@pytest.mark.asyncio
async def test_stopping_twice_changes_nothing_the_second_time(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await stop(client, interview.token)

    again = (await stop(client, interview.token)).json()

    assert again["ended"] == "STOPPED"
    assert len(await events_of(db_session, interview.interview, "STOPPED")) == 1


@pytest.mark.asyncio
async def test_an_interview_that_has_not_started_cannot_be_stopped(client, db_session, fakes, clock):
    interview = await make_strict(db_session)

    resp = await stop(client, interview.token)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_a_live_interview_has_nothing_to_stop(client, db_session, fakes, clock):
    live = await make_strict(db_session, strict=False)

    resp = await stop(client, live.token)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_the_logged_in_candidate_can_report_and_stop_too(client, db_session, fakes, clock):
    from .test_strict_interview import _logged_in_strict

    token, application = await _logged_in_strict(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    base = f"/api/v1/interviews/applications/{application.id}/strict"
    await client.post(f"{base}/start", json={"accepted": True, "rules_version": "S2"}, headers=headers)

    left = await client.post(f"{base}/event", json={"type": "left", "cause": "BLUR"}, headers=headers)
    stopped = await client.post(f"{base}/stop", headers=headers)

    assert left.json()["leaves"] == 1
    assert stopped.json()["ended"] == "STOPPED"


# ---------------------------------------------------------------------------
# The recording of an interview that ended early
# ---------------------------------------------------------------------------


@pytest.fixture
def evidence(monkeypatch):
    storage = MagicMock()
    storage.get_object_size = AsyncMock(return_value=2048)
    storage.generate_presigned_upload_url = AsyncMock(side_effect=lambda key, *_: f"https://r2.test/{key}")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: storage)
    scoring = MagicMock()
    monkeypatch.setattr(service_module, "transcribe_and_score_interview_task", scoring)
    merging = MagicMock()
    monkeypatch.setattr(service_module, "merge_interview_recording_task", merging)
    return MagicMock(storage=storage, scoring=scoring, merging=merging)


@pytest.mark.asyncio
async def test_an_interview_that_ended_still_takes_its_recording_and_keeps_the_answers(
    client, db_session, fakes, clock, evidence
):
    interview, first = await started(client, db_session)
    await answer(client, interview.token, first["turn"]["id"])
    await stop(client, interview.token)

    upload = await client.post(f"{_base(interview.token)}/upload-url")
    complete = await client.post(f"{_base(interview.token)}/complete", json={})

    assert upload.status_code == 201
    assert complete.status_code == 200
    await db_session.refresh(interview.interview)
    assert interview.interview.completed_at is not None
    assert interview.interview.r2_key == final_key(interview.interview.id, 1)
    assert LONG_ANSWER in interview.interview.transcript
    # It stays ended, and nothing is scored.
    assert interview.interview.status == InterviewStatus.STOPPED.value
    evidence.scoring.delay.assert_not_called()
    assert interview.interview.ai_score is None


@pytest.mark.asyncio
async def test_sending_the_recording_of_an_ended_interview_twice_changes_nothing(
    client, db_session, fakes, clock, evidence
):
    interview, _ = await started(client, db_session)
    await stop(client, interview.token)
    await client.post(f"{_base(interview.token)}/upload-url")
    await client.post(f"{_base(interview.token)}/complete", json={})
    await db_session.refresh(interview.interview)
    first_time = interview.interview.completed_at

    await client.post(f"{_base(interview.token)}/complete", json={})

    await db_session.refresh(interview.interview)
    assert interview.interview.completed_at == first_time


@pytest.mark.asyncio
async def test_pieces_kept_across_reloads_are_joined_for_an_ended_interview_too(
    client, db_session, fakes, clock, evidence
):
    interview, _ = await started(client, db_session)
    await client.post(f"{_base(interview.token)}/strict/recording-part")
    await stop(client, interview.token)
    await client.post(f"{_base(interview.token)}/upload-url")

    await client.post(f"{_base(interview.token)}/complete", json={})

    evidence.merging.delay.assert_called_once_with(str(interview.interview.id))


@pytest.mark.asyncio
async def test_no_join_is_queued_when_there_is_nothing_to_join(client, db_session, fakes, clock, evidence):
    interview, _ = await started(client, db_session)
    await stop(client, interview.token)
    await client.post(f"{_base(interview.token)}/upload-url")

    await client.post(f"{_base(interview.token)}/complete", json={})

    evidence.merging.delay.assert_not_called()


# ---------------------------------------------------------------------------
# Reinstating
# ---------------------------------------------------------------------------


def _headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


def _reinstate_url(interview):
    return (
        f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/reinstate"
        f"?job_id={interview.job.id}"
    )


@pytest.fixture
def invite_email(monkeypatch):
    task = MagicMock()
    monkeypatch.setattr(service_module, "send_ai_interview_invite_email", task)
    return task


async def stopped_interview(client, db_session, clock, *, after=40, with_email=True):
    interview, first = await started(client, db_session)
    clock.advance(after)
    await stop(client, interview.token)
    if with_email:
        profile = (
            await db_session.execute(
                select(TalentPoolProfiles).where(
                    TalentPoolProfiles.id == interview.interview.talent_pool_profile_id
                )
            )
        ).scalar_one()
        profile.override_email = "candidate@example.com"
        await db_session.commit()
    return interview, first


@pytest.mark.asyncio
async def test_the_owner_reinstates_and_the_candidate_carries_on_where_they_stopped_with_the_time_left(
    client, db_session, fakes, clock, invite_email
):
    interview, first = await stopped_interview(client, db_session, clock, after=100)
    clock.advance(3 * 3600)  # the employer takes three hours to decide

    resp = await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"
    assert resp.json()["interview_url"].endswith(f"/interview/{interview.token}")
    clock.advance(600)  # the candidate opens the link ten minutes later
    state = (await start(client, interview.token, accepted=False)).json()
    assert state["ended"] is None
    # The same question, with what was left when it ended: 180 - 100 seconds, not a full or an
    # expired allowance. Total: 20 minutes minus the 100 seconds used.
    assert state["turn"]["id"] == first["turn"]["id"]
    assert state["turn"]["seconds_left"] == 80
    assert state["seconds_left_total"] == settings.strict_interview_max_minutes * 60 - 100


@pytest.mark.asyncio
async def test_after_reinstating_the_leave_count_and_time_away_start_again(
    client, db_session, fakes, clock, invite_email
):
    interview, _ = await started(client, db_session)
    for _ in range(3):
        await leave_and_return(client, clock, interview.token, 8)
    await event(client, interview.token, "left", cause="HIDDEN")  # the 4th ends it
    clock.advance(60)
    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    state = (await start(client, interview.token, accepted=False)).json()

    assert state["ended"] is None
    assert state["leaves"] == 0 and state["away_seconds"] == 0
    # And the first visit after reinstating is not counted as a reload.
    assert await events_of(db_session, interview.interview, "RELOAD") == []
    # A full set of warnings again.
    for expected in (1, 2, 3):
        assert (await leave_and_return(client, clock, interview.token, 5)).json()["leaves"] == expected


@pytest.mark.asyncio
async def test_reinstating_keeps_the_history_and_marks_the_new_attempt(
    client, db_session, fakes, clock, invite_email
):
    interview, _ = await stopped_interview(client, db_session, clock)
    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    run = await run_of(db_session, interview.interview)
    kinds = [(e.kind, e.attempt) for e in await events_of(db_session, interview.interview)]

    assert run.attempt == 2 and run.ended_at is None and run.end_reason is None
    assert kinds == [("STOPPED", 1), ("REINSTATED", 1)]
    assert await status_of(db_session, interview.interview) == InterviewStatus.PENDING.value


@pytest.mark.asyncio
async def test_the_earlier_recording_is_kept_and_the_next_one_gets_its_own_file(
    client, db_session, fakes, clock, evidence, invite_email
):
    interview, _ = await stopped_interview(client, db_session, clock)
    await client.post(f"{_base(interview.token)}/upload-url")
    await client.post(f"{_base(interview.token)}/complete", json={})
    first_recording = final_key(interview.interview.id, 1)

    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    run = await run_of(db_session, interview.interview)
    await db_session.refresh(interview.interview)
    assert run.previous_recordings == [first_recording]
    assert interview.interview.r2_key is None and interview.interview.completed_at is None
    await start(client, interview.token, accepted=False)
    upload = await client.post(f"{_base(interview.token)}/upload-url")
    assert upload.status_code == 201
    await db_session.refresh(interview.interview)
    assert interview.interview.r2_key == final_key(interview.interview.id, 2) != first_recording


@pytest.mark.asyncio
async def test_the_transcript_and_its_check_are_made_again_when_it_finishes(
    client, db_session, fakes, clock, evidence, invite_email
):
    from app.modules.interviews.repository import InterviewRepository

    interview, _ = await stopped_interview(client, db_session, clock)
    await client.post(f"{_base(interview.token)}/upload-url")
    await client.post(f"{_base(interview.token)}/complete", json={})
    await InterviewRepository(db_session).create_transcript_check(interview.interview.id, "SERVER_ONLY")
    await db_session.commit()

    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    checks = (
        await db_session.execute(
            select(InterviewTranscriptCheck).where(
                InterviewTranscriptCheck.interview_id == interview.interview.id
            )
        )
    ).scalars().all()
    await db_session.refresh(interview.interview)
    assert checks == [] and interview.interview.transcript is None


@pytest.mark.asyncio
async def test_the_link_is_good_for_two_more_weeks_and_the_candidate_is_emailed_it_again(
    client, db_session, fakes, clock, invite_email
):
    interview, _ = await stopped_interview(client, db_session, clock)

    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    await db_session.refresh(interview.interview)
    assert interview.interview.token == interview.token
    assert interview.interview.token_expires_at == clock.now() + timedelta(days=14)
    kwargs = invite_email.delay.call_args.kwargs
    assert kwargs["candidate_email"] == "candidate@example.com"
    assert kwargs["interview_url"].endswith(f"/interview/{interview.token}")
    assert kwargs["strict"] is True


@pytest.mark.asyncio
async def test_reinstating_without_an_email_on_file_still_works_and_says_nothing_was_sent(
    client, db_session, fakes, clock, invite_email
):
    interview, _ = await stopped_interview(client, db_session, clock, with_email=False)

    resp = await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 200 and resp.json()["email_sent"] is False
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_reinstating_charges_nothing(client, db_session, fakes, clock, invite_email, monkeypatch):
    interview, _ = await stopped_interview(client, db_session, clock)
    charge = AsyncMock()
    monkeypatch.setattr(service_module.InterviewService, "_charge_for_invite", charge)

    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    charge.assert_not_called()


@pytest.mark.asyncio
async def test_a_teammate_in_the_same_company_may_reinstate_but_a_stranger_may_not(
    client, db_session, fakes, clock, invite_email
):
    interview, _ = await stopped_interview(client, db_session, clock)
    organization = await make_organization_for(db_session, interview.employer, company_name="Acme")
    teammate = make_employer(organization_id=organization.id)
    stranger = make_employer()
    db_session.add_all([teammate, stranger])
    await db_session.commit()

    denied = await client.post(_reinstate_url(interview), headers=_headers(stranger))
    allowed = await client.post(_reinstate_url(interview), headers=_headers(teammate))

    assert denied.status_code == 403
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_a_candidate_cannot_reinstate_their_own_interview(client, db_session, fakes, clock, invite_email):
    from .test_interview_router import register_and_promote

    interview, _ = await stopped_interview(client, db_session, clock)
    token, _user = await register_and_promote(client, db_session, "CANDIDATE")

    resp = await client.post(_reinstate_url(interview), headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 403
    assert await status_of(db_session, interview.interview) == InterviewStatus.STOPPED.value


@pytest.mark.asyncio
async def test_only_an_interview_that_ended_early_can_be_reinstated(client, db_session, fakes, clock, invite_email):
    interview, _ = await started(client, db_session)

    resp = await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 422
    assert resp.json()["code"] == "INTERVIEW_NOT_REINSTATABLE"


@pytest.mark.asyncio
async def test_an_interview_cannot_be_reinstated_twice(client, db_session, fakes, clock, invite_email):
    interview, _ = await stopped_interview(client, db_session, clock)
    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    again = await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    assert again.status_code == 422 and again.json()["code"] == "INTERVIEW_NOT_REINSTATABLE"


@pytest.mark.asyncio
async def test_it_waits_while_the_recording_is_still_being_joined(client, db_session, fakes, clock, invite_email):
    interview, _ = await stopped_interview(client, db_session, clock)
    run = await run_of(db_session, interview.interview)
    run.recording_parts = 2
    await db_session.commit()

    resp = await client.post(_reinstate_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_RECORDING_PROCESSING"
    assert await status_of(db_session, interview.interview) == InterviewStatus.STOPPED.value


@pytest.mark.asyncio
async def test_an_interview_that_is_not_theirs_is_not_found_for_the_owner(client, db_session, fakes, clock, invite_email):
    import uuid

    interview, _ = await stopped_interview(client, db_session, clock)

    resp = await client.post(
        f"/api/v1/interviews/{uuid.uuid4()}/reinstate?job_id={interview.job.id}",
        headers=_headers(interview.employer),
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_an_ended_interview_is_not_sent_the_link_again_as_a_plain_resend(
    client, db_session, fakes, clock, invite_email
):
    interview, _ = await stopped_interview(client, db_session, clock)

    resp = await client.post(
        f"/api/v1/interviews/{interview.interview.talent_pool_profile_id}/send-invite?job_id={interview.job.id}",
        headers=_headers(interview.employer),
    )

    assert resp.status_code == 200
    assert resp.json()["sent"] is False
    assert "Reinstate" in resp.json()["reason"]
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_the_candidates_screen_is_told_whether_the_interview_was_started(client, db_session, fakes, clock):
    interview = await make_strict(db_session)
    before = (await client.get(_base(interview.token))).json()
    await start(client, interview.token)
    after = (await client.get(_base(interview.token))).json()

    assert (before["started"], after["started"]) == (False, True)
    assert after["status"] == InterviewStatus.IN_PROGRESS.value


# ---------------------------------------------------------------------------
# What the employer sees
# ---------------------------------------------------------------------------


def _detail_url(interview):
    return (
        f"/api/v1/interviews/detail?job_id={interview.job.id}"
        f"&talent_pool_profile_id={interview.interview.talent_pool_profile_id}"
    )


@pytest.mark.asyncio
async def test_the_employer_sees_the_rules_accepted_the_conduct_and_each_answer_under_its_question(
    client, db_session, fakes, clock
):
    interview, first = await started(client, db_session)
    await answer(client, interview.token, first["turn"]["id"])
    await leave_and_return(client, clock, interview.token, 12, cause="FULLSCREEN")
    await event(client, interview.token, "key", key="F12")
    await stop(client, interview.token)

    resp = await client.get(_detail_url(interview), headers=_headers(interview.employer))

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "STOPPED"
    detail = body["strict"]
    assert detail["rules_version"] == "1" and detail["rules_accepted_at"]
    assert detail["ended"] == "STOPPED"
    assert (detail["leaves"], detail["away_seconds"], detail["key_presses"]) == (1, 12, 1)
    assert [e["kind"] for e in detail["events"]] == ["LEFT_PAGE", "KEY_PRESS", "STOPPED"]
    assert detail["events"][0]["detail"] == "FULLSCREEN" and detail["events"][0]["duration_seconds"] == 12
    assert detail["turns"][0]["answer"] == LONG_ANSWER and detail["turns"][0]["answered"] is True
    assert detail["turns"][1]["answer"] is None


@pytest.mark.asyncio
async def test_a_live_interviews_detail_has_no_strict_block(client, db_session, fakes, clock):
    live = await make_strict(
        db_session, strict=False, status=InterviewStatus.UPLOADED.value, transcript="AI: hi\n\nCandidate: hello"
    )

    resp = await client.get(_detail_url(live), headers=_headers(live.employer))

    assert resp.status_code == 200 and resp.json()["strict"] is None


@pytest.mark.asyncio
async def test_only_the_jobs_company_can_see_an_ended_interviews_detail(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    await stop(client, interview.token)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.commit()

    resp = await client.get(_detail_url(interview), headers=_headers(stranger))

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_the_candidate_never_receives_the_employers_notes_about_them(client, db_session, fakes, clock):
    interview, _ = await started(client, db_session)
    for _ in range(3):
        await leave_and_return(client, clock, interview.token, 5)

    state = (await event(client, interview.token, "ping")).json()

    # What the candidate's screen is told: counts and the warning limits, never the timeline.
    assert set(state) == {
        "interview_id", "finished", "turn", "total_questions", "seconds_left_total",
        "max_seconds_total", "ended", "leaves", "max_leaves", "away_seconds",
        "max_away_seconds", "key_presses",
    }


# ---------------------------------------------------------------------------
# Scoring an interview that ended early (only when the employer asks)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_employer_can_ask_for_a_score_of_an_ended_interview_once_its_recording_is_in(
    client, db_session, fakes, clock, evidence, monkeypatch
):
    async def allowed(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service_module, "assert_can_score_interviews", allowed)
    interview, _ = await started(client, db_session)
    await stop(client, interview.token)
    await client.post(f"{_base(interview.token)}/upload-url")
    await client.post(f"{_base(interview.token)}/complete", json={})

    resp = await client.post(
        f"/api/v1/interviews/score?job_id={interview.job.id}"
        f"&talent_pool_profile_id={interview.interview.talent_pool_profile_id}",
        headers=_headers(interview.employer),
    )

    assert resp.status_code == 202
    evidence.scoring.delay.assert_called_once()
    assert await status_of(db_session, interview.interview) == InterviewStatus.UPLOADED.value


@pytest.mark.asyncio
async def test_a_score_cannot_be_asked_for_before_the_recording_of_an_ended_interview_arrived(
    client, db_session, fakes, clock, evidence, monkeypatch
):
    async def allowed(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service_module, "assert_can_score_interviews", allowed)
    interview, _ = await started(client, db_session)
    await stop(client, interview.token)

    resp = await client.post(
        f"/api/v1/interviews/score?job_id={interview.job.id}"
        f"&talent_pool_profile_id={interview.interview.talent_pool_profile_id}",
        headers=_headers(interview.employer),
    )

    assert resp.status_code == 422 and resp.json()["code"] == "INTERVIEW_PROCESSING"
    evidence.scoring.delay.assert_not_called()
    assert await status_of(db_session, interview.interview) == InterviewStatus.STOPPED.value


@pytest.mark.asyncio
async def test_a_finished_interview_that_was_reinstated_is_scored_as_normal(
    client, db_session, fakes, clock, evidence, invite_email
):
    interview, first = await stopped_interview(client, db_session, clock)
    await client.post(_reinstate_url(interview), headers=_headers(interview.employer))
    state = (await start(client, interview.token, accepted=False)).json()
    await answer(client, interview.token, state["turn"]["id"])
    interview.interview.r2_key = None
    await client.post(f"{_base(interview.token)}/upload-url")
    # Finish every remaining question.
    current = (await start(client, interview.token, accepted=False)).json()
    while current["turn"] is not None:
        current = (await answer(client, interview.token, current["turn"]["id"])).json()

    resp = await client.post(f"{_base(interview.token)}/complete", json={})

    assert resp.status_code == 200
    await db_session.refresh(interview.interview)
    assert interview.interview.status == InterviewStatus.UPLOADED.value
    evidence.scoring.delay.assert_called_once()


# ---------------------------------------------------------------------------
# A recording that is still being put together from its pieces
# ---------------------------------------------------------------------------


@pytest.fixture
def signed(monkeypatch):
    """A recording link without touching real storage."""
    storage = MagicMock()
    storage.generate_presigned_url = AsyncMock(return_value="https://signed.example/video")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: storage)
    return storage


async def finished_in_pieces(db_session, clock, *, parts=0, previous=None):
    interview = await make_strict(
        db_session,
        status=InterviewStatus.UPLOADED.value,
        r2_key="interviews/x/recording.webm",
        completed_at=clock.now(),
        transcript="AI: q\n\nCandidate: a",
    )
    run = await run_of(db_session, interview.interview)
    run.recording_parts = parts
    run.previous_recordings = previous
    await db_session.commit()
    return interview


async def detail_of(client, interview):
    return (await client.get(_detail_url(interview), headers=_headers(interview.employer))).json()


@pytest.mark.asyncio
async def test_while_the_pieces_are_being_joined_no_video_is_shown_and_the_employer_is_told(
    client, db_session, fakes, clock, signed
):
    interview = await finished_in_pieces(db_session, clock, parts=1)

    body = await detail_of(client, interview)

    assert body["video_url"] is None
    assert body["strict"]["recording_pending"] is True
    assert body["strict"]["recording_partial"] is False
    signed.generate_presigned_url.assert_not_called()


@pytest.mark.asyncio
async def test_an_interview_the_employer_reinstated_is_also_waiting_for_its_pieces(
    client, db_session, fakes, clock, signed
):
    interview = await finished_in_pieces(db_session, clock, previous=["interviews/x/recording.webm.attempt1"])

    body = await detail_of(client, interview)

    assert body["video_url"] is None and body["strict"]["recording_pending"] is True


@pytest.mark.asyncio
async def test_once_the_pieces_are_joined_the_whole_video_is_shown(client, db_session, fakes, clock, signed):
    interview = await finished_in_pieces(db_session, clock)

    body = await detail_of(client, interview)

    assert body["video_url"] == "https://signed.example/video"
    assert body["strict"]["recording_pending"] is False and body["strict"]["recording_partial"] is False


@pytest.mark.asyncio
async def test_if_the_joining_never_happens_the_last_piece_is_shown_marked_as_partial(
    client, db_session, fakes, clock, signed
):
    interview = await finished_in_pieces(db_session, clock, parts=1)
    clock.advance(31 * 60)

    body = await detail_of(client, interview)

    assert body["video_url"] == "https://signed.example/video"
    assert body["strict"]["recording_pending"] is False
    assert body["strict"]["recording_partial"] is True


@pytest.mark.asyncio
async def test_the_shared_link_does_not_show_a_half_joined_video_either(db_session, signed):
    from tests.interview_share.test_shared_results import results, setup_job
    from tests.interview_share.test_shared_strict import strict_candidate

    employer, job = await setup_job(db_session)
    row, run = await strict_candidate(db_session, employer, job, "Ada Obi", status="SCORED", ai_score=70, ai_rationale="Fine.", transcript="AI: q\n\nCandidate: a")
    run.recording_parts = 1
    row.completed_at = datetime.now(UTC)
    await db_session.flush()

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.video_url is None
    assert candidate.strict.recording_pending is True


def test_a_not_started_run_has_no_open_leave_when_created():
    run = StrictInterviewRun(interview_id=None)

    assert run.away_since is None and run.ended_at is None and run.end_reason is None


def test_the_conduct_numbers_come_from_settings():
    assert settings.strict_max_leaves == 4
    assert settings.strict_max_away_seconds == 60
    # The unused-import guard for names used only by other tests in this module.
    assert ValidationException and Interview
