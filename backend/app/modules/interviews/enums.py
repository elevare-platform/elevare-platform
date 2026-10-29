"""Enumerations for AI video interviews."""

from datetime import UTC, datetime, timedelta
from enum import Enum

# An interview stuck IN_PROGRESS with no activity (session start/restart,
# upload, complete — anything that touches updated_at) for longer than
# this is treated as abandoned: a closed tab or crashed browser mid-
# interview, which the backend has no other way to detect since the live
# WebRTC session goes straight from the candidate's browser to OpenAI.
# The max interview length itself is much shorter (settings.
# interview_max_duration_minutes), so this generously covers a real
# session plus upload time before calling it abandoned.
STALE_INTERVIEW_TIMEOUT = timedelta(hours=2)
# An interview that reached the upload step (its recording address was issued) is waiting for a
# recording, not abandoned: the candidate is retrying on a poor connection or will come back.
# The employer's "Resend" and the candidate's retry both work while it is in progress, so it is
# given this long before it is marked failed.
STALE_UPLOAD_TIMEOUT = timedelta(days=3)
# A strict interview that is still IN_PROGRESS can be started over by the employer (a fresh interview
# on a new link) only once the candidate has not been heard from for this long. A candidate who is
# answering is heard from at every answer and every page visit, so this keeps a click from throwing
# away someone who is working, while one whose laptop froze or whose connection died is not stuck
# for the two hours it takes the stale sweep to give up.
IN_PROGRESS_QUIET_AFTER = timedelta(minutes=10)


class InterviewStatus(str, Enum):
    """Lifecycle states for a candidate's live AI video interview."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    UPLOADED = "UPLOADED"
    SCORED = "SCORED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    # A strict interview the system ended (too many leaves, or too long away), or that the
    # candidate stopped with "I need to stop". Neither is scored on its own; the employer can
    # reinstate it, and the candidate then carries on where they stopped.
    ENDED_CONDUCT = "ENDED_CONDUCT"
    STOPPED = "STOPPED"


# The two "ended early" statuses of a strict interview.
ENDED_STATUSES = (InterviewStatus.ENDED_CONDUCT.value, InterviewStatus.STOPPED.value)


class ConductEventKind(str, Enum):
    """What a row of a strict interview's timeline records."""

    LEFT_PAGE = "LEFT_PAGE"  # the page hidden, the window out of focus, or full screen exited
    RELOAD = "RELOAD"  # the page was reloaded or came back after being closed
    KEY_PRESS = "KEY_PRESS"  # a key that tries to leave (Esc, Alt, F11...), warned, never counted
    STOPPED = "STOPPED"  # the candidate pressed "I need to stop"
    ENDED = "ENDED"  # the system ended the interview
    REINSTATED = "REINSTATED"  # the employer reinstated it


# What ended an interview (the detail of an ENDED event, and the run's ``end_reason``).
END_TOO_MANY_LEAVES = "TOO_MANY_LEAVES"
END_TOO_LONG_AWAY = "TOO_LONG_AWAY"
END_STOPPED = "STOPPED"


class TurnKind(str, Enum):
    """What a turn of a strict interview is: one of the job's questions, or a follow-up to it."""

    QUESTION = "QUESTION"
    FOLLOW_UP = "FOLLOW_UP"


class FollowUpMode(str, Enum):
    """What the AI may do after an answer in a job's strict interview (docs/08_DECISIONS.md, item
    40). The employer chooses it per job; the same for every candidate of the job.

    ``NONE``: only the questions on screen, no follow-up. ``STANDARD``: up to
    ``strict_max_follow_ups`` neutral follow-ups, preferring the question's prepared probes when
    one fits. ``PROBES_ONLY``: a follow-up only from the probes the employer wrote for that
    question, never one the AI makes up.
    """

    NONE = "NONE"
    STANDARD = "STANDARD"
    PROBES_ONLY = "PROBES_ONLY"


class PanelDecision(str, Enum):
    """What a hiring panel decides about a candidate after an interview (the client's assessment
    record: strong shortlist, shortlist, hold, do not shortlist). A person's decision, recorded with
    a rationale and a sign-off. It stops at the shortlist: hiring is outside the platform's scope."""

    STRONG_SHORTLIST = "STRONG_SHORTLIST"
    SHORTLIST = "SHORTLIST"
    HOLD = "HOLD"
    DO_NOT_SHORTLIST = "DO_NOT_SHORTLIST"


PANEL_DECISION_LABELS = {
    PanelDecision.STRONG_SHORTLIST.value: "Strong shortlist",
    PanelDecision.SHORTLIST.value: "Shortlist",
    PanelDecision.HOLD.value: "Hold",
    PanelDecision.DO_NOT_SHORTLIST.value: "Do not shortlist",
}


def follow_up_mode_of(value: str | None) -> "FollowUpMode":
    """A stored value as a mode; nothing stored, or anything unknown, is the standard."""
    try:
        return FollowUpMode(value) if value else FollowUpMode.STANDARD
    except ValueError:
        return FollowUpMode.STANDARD


class TranscriptCheckStatus(str, Enum):
    """Outcome of comparing the candidate-device transcript with a server-side
    transcription of the recording."""

    VERIFIED = "VERIFIED"  # the two agree closely enough
    MISMATCH = "MISMATCH"  # they clearly disagree; the server transcript is trusted
    UNAVAILABLE = "UNAVAILABLE"  # could not be checked (transcription failed, too little text)
    SERVER_ONLY = "SERVER_ONLY"  # no submitted transcript; the recording's own is the transcript


class InterviewCostComponent(str, Enum):
    """Which billed external call an InterviewCost row is for."""

    REALTIME = "realtime"
    TRANSCRIPTION = "transcription"
    SCORING = "scoring"


def compute_display_status(
    status: str, token_expires_at: datetime | None
) -> str:
    """Effective status for display — EXPIRED is never persisted to the row.

    A sent-but-never-opened invite otherwise sits at PENDING forever, even
    long after its token has actually gone stale, with nothing prompting
    the employer to resend. Computing it at read time (instead of a sweep
    that writes EXPIRED to the row) keeps this always accurate with no
    extra Celery task and no risk of it drifting out of sync with the
    token's real expiry.
    """
    if (
        status == InterviewStatus.PENDING.value
        and token_expires_at is not None
        and token_expires_at < datetime.now(UTC)
    ):
        return InterviewStatus.EXPIRED.value
    return status
