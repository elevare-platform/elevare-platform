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


class InterviewStatus(str, Enum):
    """Lifecycle states for a candidate's live AI video interview."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    UPLOADED = "UPLOADED"
    SCORED = "SCORED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


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
