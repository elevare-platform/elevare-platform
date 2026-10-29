"""Leaving the screen, warnings, ending, stopping and reinstating a strict interview.

The rules (docs/08_DECISIONS.md, "The new strict, text-only AI interview", item 25):

* Leaving is the page hidden, the window out of focus or full screen exited. The browser sends
  "left" once a leave has lasted a second, and "returned" when it is over. The SERVER times the
  leave with its own clock, so the browser cannot shorten one.
* The 1st to 3rd leave warns. The 4th leave, or 60 seconds away in total, ends the interview.
  A leave still open counts towards the 60 seconds the next time the server hears from the
  candidate, so closing the tab does not stop the clock.
* A reload counts as one leave, timed from the last time the screen was heard from.
* Key presses that try to leave (Esc, Alt, F11...) are recorded and warned about, and never
  count towards ending.
* "I need to stop" ends the interview as STOPPED: the candidate's own choice, not conduct.
* Either ending keeps everything: the recording, the answers and the timeline. An employer who
  owns the job can reinstate it, and the candidate carries on where they stopped, with the time
  they had left when it ended.

This is a mixin of ``StrictInterviewService``: it uses the service's database session,
repository and ``_state``.
"""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.exceptions import ValidationException
from app.core.schema_guard import tolerate_missing
from app.modules.interviews.enums import (
    END_STOPPED,
    END_TOO_LONG_AWAY,
    END_TOO_MANY_LEAVES,
    ENDED_STATUSES,
    ConductEventKind,
    InterviewStatus,
)
from app.modules.interviews.models import (
    Interview,
    InterviewConductEvent,
    InterviewScoreReview,
    InterviewTranscriptCheck,
    InterviewTurn,
    InterviewWeightedScore,
    StrictInterviewRun,
)

logger = logging.getLogger(__name__)

EVENT_TYPES = {"ping", "left", "returned", "key"}
# Why the page was left: hidden (another tab or app), the window lost focus, full screen exited.
LEAVE_CAUSES = {"HIDDEN", "BLUR", "FULLSCREEN"}
# A page that comes back this soon after it was last heard from is a duplicate request (a double
# click, a second tab), not a reload.
RELOAD_MIN_GAP_SECONDS = 3
# More key presses than this in one attempt are not stored (a held key must not fill the table).
MAX_KEY_EVENTS = 100
# How long a reinstated interview's link works from the moment of reinstating.
REINSTATE_LINK_DAYS = 14
# How long after an interview finishes its pieces are expected to be joined (a copy join takes
# seconds; a re-encode of a long video can take many minutes). After this the joining is taken
# to have failed.
RECORDING_JOIN_GRACE_SECONDS = 30 * 60
# A key or a whole combination, such as "Escape" or "Ctrl+Shift+I" (the longest the screen makes,
# Ctrl+Alt+Shift+Meta+Backspace, is 29 characters; the column holds 40).
_KEY_NAME = re.compile(r"^[A-Za-z0-9+ ]{1,40}$")


def _seconds(later: datetime, earlier: datetime) -> float:
    return max(0.0, (later - earlier).total_seconds())


class ConductMixin:
    """The conduct half of ``StrictInterviewService``."""

    # ------------------------------------------------------------------
    # The timeline
    # ------------------------------------------------------------------

    async def _events(
        self, interview_id: uuid.UUID, attempt: int | None = None
    ) -> list[InterviewConductEvent]:
        query = select(InterviewConductEvent).where(
            InterviewConductEvent.interview_id == interview_id
        )
        if attempt is not None:
            query = query.where(InterviewConductEvent.attempt == attempt)
        result = await self._db.execute(
            query.order_by(InterviewConductEvent.occurred_at, InterviewConductEvent.created_at)
        )
        return list(result.scalars().all())

    def _add_event(
        self,
        interview_id: uuid.UUID,
        run: StrictInterviewRun,
        kind: ConductEventKind,
        *,
        at: datetime,
        detail: str | None = None,
        counted: bool = False,
        duration: float | None = None,
    ) -> InterviewConductEvent:
        event = InterviewConductEvent(
            interview_id=interview_id,
            attempt=run.attempt,
            kind=kind.value,
            detail=detail,
            occurred_at=at,
            duration_seconds=duration,
            counted=counted,
        )
        self._db.add(event)
        return event

    async def _conduct_summary(
        self, interview_id: uuid.UUID, run: StrictInterviewRun, now: datetime
    ) -> dict:
        """What counts so far in this attempt. A leave still open adds the time it has lasted."""
        leaves = 0
        away = 0.0
        keys = 0
        reloads = 0
        for event in await self._events(interview_id, run.attempt):
            if event.kind in (ConductEventKind.LEFT_PAGE.value, ConductEventKind.RELOAD.value):
                if event.counted:
                    leaves += 1
                away += event.duration_seconds or 0.0
                if event.kind == ConductEventKind.RELOAD.value:
                    reloads += 1
            elif event.kind == ConductEventKind.KEY_PRESS.value:
                keys += 1
        if run.away_since is not None:
            away += _seconds(now, run.away_since)
        return {"leaves": leaves, "away_seconds": away, "key_presses": keys, "reloads": reloads}

    @staticmethod
    def _reason_to_end(summary: dict) -> str | None:
        if summary["leaves"] >= settings.strict_max_leaves:
            return END_TOO_MANY_LEAVES
        if summary["away_seconds"] >= settings.strict_max_away_seconds:
            return END_TOO_LONG_AWAY
        return None

    async def _close_leave(self, interview_id: uuid.UUID, run: StrictInterviewRun, now: datetime) -> None:
        """The open leave is over: give it the length the server timed."""
        if run.away_since is None:
            return
        result = await self._db.execute(
            select(InterviewConductEvent)
            .where(
                InterviewConductEvent.interview_id == interview_id,
                InterviewConductEvent.attempt == run.attempt,
                InterviewConductEvent.kind == ConductEventKind.LEFT_PAGE.value,
                InterviewConductEvent.duration_seconds.is_(None),
            )
            .order_by(InterviewConductEvent.occurred_at.desc())
            .limit(1)
        )
        event = result.scalar_one_or_none()
        if event is not None:
            event.duration_seconds = _seconds(now, run.away_since)
        run.away_since = None
        run.away_kind = None

    # ------------------------------------------------------------------
    # Ending
    # ------------------------------------------------------------------

    async def _end(
        self, interview: Interview, run: StrictInterviewRun, reason: str, now: datetime
    ) -> None:
        """End (or stop) the interview. Nothing is thrown away: the turns, the timeline and the
        recording stay, for the employer to look at and, if they choose, to reinstate."""
        await self._close_leave(interview.id, run, now)
        stopped = reason == END_STOPPED
        self._add_event(
            interview.id,
            run,
            ConductEventKind.STOPPED if stopped else ConductEventKind.ENDED,
            at=now,
            detail=reason,
        )
        run.ended_at = now
        run.end_reason = reason
        await self._repo.update(
            interview.id,
            {"status": InterviewStatus.STOPPED.value if stopped else InterviewStatus.ENDED_CONDUCT.value},
        )
        await self._notify_employer(interview, reason)

    async def _notify_employer(self, interview: Interview, reason: str) -> None:
        """Tell whoever created the job, in the app, that an interview ended early. The
        employer decides what happens next: reinstating it, or leaving it."""
        from app.modules.interviews.service import resolve_candidate_name
        from app.modules.notifications.repository import NotificationRepository

        # The repository's update refreshed the interview, which expires what it had loaded
        # (the job, the candidate), so read it again with those loaded.
        interview = await self._repo.get_by_id(interview.id)
        job = interview.job
        name = resolve_candidate_name(interview.talent_pool_profile) or "A candidate"
        if reason == END_STOPPED:
            title = f"{name} stopped their interview"
            body = (
                f"{name} chose to stop their interview for {job.title}. You can look at what "
                "was recorded and, if you wish, reinstate it so they can carry on."
            )
        else:
            title = f"{name}'s interview ended early"
            body = (
                f"{name}'s interview for {job.title} ended because they left the interview "
                "screen too often or for too long. The notes are for you to review, they are "
                "not proof of anything. You can reinstate it so they can carry on."
            )
        await NotificationRepository(self._db).create(
            recipient_id=job.employer_id,
            type="AI_INTERVIEW_ENDED",
            title=title,
            body=body,
            entity_type="JOB",
            entity_id=job.id,
            context={
                "job_id": str(job.id),
                "talent_pool_profile_id": str(interview.talent_pool_profile_id),
            },
        )

    # ------------------------------------------------------------------
    # What the screen reports
    # ------------------------------------------------------------------

    async def note_return(
        self, interview: Interview, run: StrictInterviewRun, now: datetime
    ) -> None:
        """The candidate's page has just come back (a reload, or the link opened again): time
        the gap as one leave, then see whether that is the one that ends the interview."""
        if run.away_since is not None:
            # They went away, and the page never said it was back: that leave ends now.
            await self._close_leave(interview.id, run, now)
        elif (
            run.last_seen_at is not None
            and _seconds(now, run.last_seen_at) >= RELOAD_MIN_GAP_SECONDS
        ):
            self._add_event(
                interview.id,
                run,
                ConductEventKind.RELOAD,
                at=now,
                counted=True,
                duration=_seconds(now, run.last_seen_at),
            )
        run.last_seen_at = now
        await self._db.flush()
        reason = self._reason_to_end(await self._conduct_summary(interview.id, run, now))
        if reason:
            await self._end(interview, run, reason, now)

    async def record_event(
        self,
        interview: Interview,
        *,
        event_type: str,
        cause: str | None = None,
        key: str | None = None,
    ) -> dict:
        """One thing the candidate's screen reports: it is still there (ping), the page was
        left (left), it is back (returned), or a key that tries to leave was pressed (key).
        Returns the state, which says whether this ended the interview and how many warnings
        have been used."""
        if event_type not in EVENT_TYPES:
            raise ValidationException("That is not something this interview records.")
        status = await self._repo.lock_status(interview.id)
        run = await self.get_run(interview.id)
        if run is None or run.started_at is None:
            raise ValidationException("This interview has not been started.")
        now = self._clock()
        turns = await self._turns(interview.id)
        if status in ENDED_STATUSES:
            return await self._state(interview, run, turns, now)
        if status != InterviewStatus.IN_PROGRESS.value:
            raise ValidationException("This interview is not in progress.")

        if event_type == "left" and run.away_since is None:
            run.away_since = now
            run.away_kind = cause if cause in LEAVE_CAUSES else "HIDDEN"
            self._add_event(
                interview.id, run, ConductEventKind.LEFT_PAGE,
                at=now, detail=run.away_kind, counted=True,
            )
        elif event_type == "returned" and run.away_since is not None:
            await self._close_leave(interview.id, run, now)
        elif event_type == "key":
            kept = [e for e in await self._events(interview.id, run.attempt)
                    if e.kind == ConductEventKind.KEY_PRESS.value]
            if len(kept) < MAX_KEY_EVENTS:
                name = key if key and _KEY_NAME.match(key) else "Other"
                self._add_event(
                    interview.id, run, ConductEventKind.KEY_PRESS, at=now, detail=name
                )
        run.last_seen_at = now
        await self._db.flush()

        reason = self._reason_to_end(await self._conduct_summary(interview.id, run, now))
        if reason:
            await self._end(interview, run, reason, now)
        await self._db.commit()
        return await self._state(interview, run, turns, now)

    async def stop(self, interview: Interview) -> dict:
        """The candidate pressed "I need to stop" and confirmed. Ends the interview as their
        own choice, not as conduct."""
        status = await self._repo.lock_status(interview.id)
        run = await self.get_run(interview.id)
        if run is None or run.started_at is None:
            raise ValidationException("This interview has not been started.")
        now = self._clock()
        turns = await self._turns(interview.id)
        if status in ENDED_STATUSES:
            return await self._state(interview, run, turns, now)
        if status != InterviewStatus.IN_PROGRESS.value:
            raise ValidationException("This interview is not in progress.")
        run.last_seen_at = now
        await self._end(interview, run, END_STOPPED, now)
        await self._db.commit()
        return await self._state(interview, run, turns, now)

    # ------------------------------------------------------------------
    # Reinstating (the employer)
    # ------------------------------------------------------------------

    async def reinstate(self, interview: Interview) -> Interview:
        """Let the candidate carry on where they stopped. The caller has already checked that
        the employer may manage this job.

        The time left when it ended is what they get (the clock was paused), the answers stay,
        the leave count and the time away start again, and nothing more is charged. The earlier
        recording is kept as its own clip (the next attempt records a new one), and the timeline
        keeps everything.
        """
        status = await self._repo.lock_status(interview.id)
        if status not in ENDED_STATUSES:
            raise ValidationException(
                "Only an interview that ended early can be reinstated.",
                code="INTERVIEW_NOT_REINSTATABLE",
            )
        run = await self.get_run(interview.id)
        if run is None or run.ended_at is None:
            raise ValidationException(
                "Only an interview that ended early can be reinstated.",
                code="INTERVIEW_NOT_REINSTATABLE",
            )
        if run.recording_parts > 0:
            raise ValidationException(
                "The recording of this interview is still being prepared. Please try again in a minute.",
                code="INTERVIEW_RECORDING_PROCESSING",
            )
        if self._nothing_left_to_do(run, await self._turns(interview.id), run.ended_at):
            # Seen on a real test: the last answer was sent as the interview ended, so the
            # candidate came back to a finished interview with nothing to record or answer.
            raise ValidationException(
                "This candidate had already answered every question, or the time had run out, "
                "so there is nothing left to carry on with. Use \"Score what was recorded\" instead.",
                code="INTERVIEW_NOTHING_LEFT",
            )
        await self._db.refresh(interview)
        now = self._clock()

        # The clock stays stopped until the candidate opens the link again (see ``resume_clock``):
        # whatever was left when it ended is what they get, however long the employer and the
        # candidate take.
        run.paused_at = run.ended_at

        if interview.r2_key:
            run.previous_recordings = [*(run.previous_recordings or []), interview.r2_key]
        self._add_event(
            interview.id, run, ConductEventKind.REINSTATED, at=now, detail=run.end_reason
        )
        run.attempt += 1
        run.ended_at = None
        run.end_reason = None
        run.away_since = None
        run.away_kind = None
        # Not heard from yet: the candidate's first visit must not count as a reload.
        run.last_seen_at = None

        # The transcript and its check are made again when the interview finishes.
        await self._db.execute(
            delete(InterviewTranscriptCheck).where(
                InterviewTranscriptCheck.interview_id == interview.id
            )
        )
        updated = await self._repo.update(
            interview.id,
            {
                "status": InterviewStatus.PENDING.value,
                "r2_key": None,
                "transcript": None,
                "completed_at": None,
                "video_expires_at": None,
                "token_expires_at": now + timedelta(days=REINSTATE_LINK_DAYS),
            },
        )
        await self._db.commit()
        return updated

    async def _failed_before_finishing(
        self,
        interview: Interview,
        *,
        allow_ended: bool = False,
        allow_completed: bool = False,
    ) -> StrictInterviewRun:
        """The run of an interview that failed before it was finished, with the row locked.

        An interview becomes FAILED without ever being completed when its recording never
        arrived and the stale sweep gave up on it. Everything else that is FAILED (scoring
        failed after the recording arrived) has a completion time and is not this. With
        ``allow_ended`` an interview that ended early (not scored) also qualifies, for a
        retake; it is otherwise carried on with by reinstating it. With ``allow_completed`` a
        finished interview (scored, or whose scoring failed) qualifies too, for a retake the
        employer asks for; one still being scored does not, since the scoring would then land
        on the new attempt.
        """
        status = await self._repo.lock_status(interview.id)
        await self._db.refresh(interview)
        run = await self.get_run(interview.id)
        failed = (
            status == InterviewStatus.FAILED.value and interview.completed_at is None
        )
        ended = allow_ended and status in ENDED_STATUSES
        completed = allow_completed and (
            status == InterviewStatus.SCORED.value
            or (status == InterviewStatus.FAILED.value and interview.completed_at is not None)
        )
        if not (failed or ended or completed) or run is None or run.started_at is None:
            raise ValidationException(
                "Only an interview that was started and then finished, ended early or failed can be "
                "started over."
                if allow_completed
                else "Only an interview that was started but never finished can be recovered.",
                code="INTERVIEW_NOT_RECOVERABLE",
            )
        return run

    async def reopen_failed(self, interview: Interview) -> Interview:
        """Let the candidate finish an interview that failed before it was finished: they open
        the link again and the recording their browser kept is sent. The caller has already
        checked that the employer may manage this job and has taken the payment.

        The clock stands still from the last thing the candidate did until they open the link
        (the same rule as a reinstated interview), the answers stay, and the recording that was
        never received is forgotten so no clip points at a file that is not there.
        """
        run = await self._failed_before_finishing(interview)
        turns = await self._turns(interview.id)
        now = self._clock()

        moments = [run.last_seen_at, run.started_at]
        for turn in turns:
            moments.append(turn.answered_at or turn.opened_at)
        run.paused_at = max(moment for moment in moments if moment is not None)
        run.ended_at = None
        run.end_reason = None
        run.away_since = None
        run.away_kind = None
        # Not heard from yet: the candidate's first visit must not count as a reload.
        run.last_seen_at = None

        updated = await self._repo.update(
            interview.id,
            {
                "status": InterviewStatus.PENDING.value,
                "r2_key": None,
                "token": interview.token or secrets.token_urlsafe(32),
                "token_expires_at": now + timedelta(days=REINSTATE_LINK_DAYS),
                "session_start_count": 0,
                "reset_requested_at": None,
            },
        )
        await self._db.commit()
        return updated

    async def start_over(self, interview: Interview) -> Interview:
        """Give the candidate a fresh interview in place of one that failed before it was
        finished: new questions copied when they start, a new clock, no answers. Used when the
        recording of the first attempt is gone, so what is left of it could not be reviewed. The
        caller has already checked that the employer may manage this job and has taken the
        payment.

        Also used for an interview that ended early (or was stopped), when the employer would
        rather have the candidate take it again than reinstate it: everything of the attempt is
        discarded, the recording included (the caller removes the files).

        And for a COMPLETED interview (scored, or whose scoring failed) the employer lets the
        candidate take again, for example after a low score: the score, its report and the
        written assessment are discarded with the answers. What is kept: the cost rows (real
        spend), and the hiring panel's decisions, an append-only record of what the company
        decided at the time (each carries its date)."""
        run = await self._failed_before_finishing(
            interview, allow_ended=True, allow_completed=True
        )
        now = self._clock()

        for model in (
            InterviewTurn,
            InterviewConductEvent,
            InterviewTranscriptCheck,
            InterviewWeightedScore,
        ):
            await self._db.execute(delete(model).where(model.interview_id == interview.id))

        # An Elevare reviewer's score belonged to the attempt being discarded. (Skipped in the
        # seconds of a deploy before its table exists.)
        async def drop_reviews() -> None:
            await self._db.execute(
                delete(InterviewScoreReview).where(InterviewScoreReview.interview_id == interview.id)
            )

        await tolerate_missing(self._db, drop_reviews, None)

        run.rules_version = None
        run.rules_accepted_at = None
        run.questions = None
        run.follow_up_mode = None
        run.started_at = None
        run.recording_parts = 0
        run.attempt = 1
        run.last_seen_at = None
        run.away_since = None
        run.away_kind = None
        run.ended_at = None
        run.end_reason = None
        run.paused_at = None
        run.previous_recordings = None

        updated = await self._repo.update(
            interview.id,
            {
                "status": InterviewStatus.PENDING.value,
                "r2_key": None,
                "transcript": None,
                "ai_score": None,
                "ai_rationale": None,
                "ai_scored_at": None,
                "started_at": None,
                "completed_at": None,
                "video_expires_at": None,
                "token": interview.token or secrets.token_urlsafe(32),
                "token_expires_at": now + timedelta(days=REINSTATE_LINK_DAYS),
                "session_start_count": 0,
                "reset_requested_at": None,
            },
        )
        await self._db.commit()
        return updated

    async def resume_clock(
        self, run: StrictInterviewRun, turns: list[InterviewTurn], now: datetime
    ) -> None:
        """The candidate has opened the link of a reinstated interview: start the clock again.
        The interview's start and the open question move forward by the time that went by, so
        they have exactly what was left when it ended."""
        if run.paused_at is None:
            return
        paused = now - run.paused_at
        if turns and turns[-1].answered_at is None:
            turns[-1].opened_at = turns[-1].opened_at + paused
        run.started_at = run.started_at + paused
        run.paused_at = None

    # ------------------------------------------------------------------
    # What the employer sees
    # ------------------------------------------------------------------

    @staticmethod
    def _recording_state(interview: Interview, run: StrictInterviewRun, now: datetime) -> dict:
        """Whether the recording is still being put together from its pieces.

        Pieces exist when the candidate reloaded during this attempt (parts). Once the interview
        has finished they are joined by a worker; until then the recording on file is only the
        last piece, so the screen must not show it as if it were all. If the joining has not
        happened after ``RECORDING_JOIN_GRACE_SECONDS`` it has evidently failed and the last
        piece is shown with a warning that it is only part of the interview. The recordings of
        earlier attempts (reinstated interview) are separate clips and are never "in pieces".
        """
        in_pieces = run.recording_parts > 0
        if not in_pieces or interview.completed_at is None:
            return {"recording_pending": False, "recording_partial": False}
        waiting = _seconds(now, interview.completed_at) < RECORDING_JOIN_GRACE_SECONDS
        return {"recording_pending": waiting, "recording_partial": not waiting}

    async def strict_detail(self, interview: Interview) -> dict | None:
        """Everything about a strict interview that the employer and the shared link show next
        to the recording: the rules accepted, the conduct summary, the timeline, how it ended,
        and each answer under its question. None for a live interview."""
        run = await self.get_run(interview.id)
        if run is None:
            return None
        now = self._clock()
        summary = await self._conduct_summary(interview.id, run, now)
        events = await self._events(interview.id)
        result = await self._db.execute(
            select(InterviewTurn)
            .where(InterviewTurn.interview_id == interview.id)
            .order_by(InterviewTurn.position)
        )
        return {
            "rules_version": run.rules_version,
            "rules_accepted_at": run.rules_accepted_at,
            "attempt": run.attempt,
            "ended": run.end_reason,
            "ended_at": run.ended_at,
            "leaves": summary["leaves"],
            "away_seconds": int(round(summary["away_seconds"])),
            "key_presses": summary["key_presses"],
            "reloads": summary["reloads"],
            **self._recording_state(interview, run, now),
            "events": [
                {
                    "kind": event.kind,
                    "detail": event.detail,
                    "occurred_at": event.occurred_at,
                    "duration_seconds": (
                        int(round(event.duration_seconds)) if event.duration_seconds is not None else None
                    ),
                    "attempt": event.attempt,
                    "counted": event.counted,
                }
                for event in events
            ],
            "turns": [
                {
                    "number": turn.question_number,
                    "kind": turn.kind,
                    "question": turn.question_text,
                    "answer": turn.answer_text,
                    "answered": turn.answered_at is not None,
                }
                for turn in result.scalars().all()
            ],
        }
