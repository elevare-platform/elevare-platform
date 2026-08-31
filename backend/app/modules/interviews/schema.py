"""Pydantic request and response schemas for the interviews module."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class InterviewSessionResponse(BaseModel):
    """A short-lived Realtime API session the candidate's browser connects with directly."""

    interview_id: uuid.UUID
    client_secret: str
    expires_at: datetime
    realtime_model: str
    max_duration_minutes: int


class InterviewUploadUrlResponse(BaseModel):
    """A short-lived URL the candidate's browser uploads the recorded video to directly."""

    upload_url: str
    expires_in_seconds: int


class RealtimeUsageDetail(BaseModel):
    """Accumulated OpenAI Realtime API usage across the session, as reported by the frontend.

    The backend never sees the live WebRTC connection (the browser talks
    directly to OpenAI) — this is the only way real per-interview realtime
    cost data reaches the server, accumulated client-side from
    ``response.done`` events on the same data channel already used to
    capture the transcript.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    input_token_details: dict | None = None
    output_token_details: dict | None = None


class InterviewCompleteRequest(BaseModel):
    """Optional payload accompanying upload completion.

    ``transcript`` is the diarized dialogue assembled client-side from
    Realtime API transcript events during the live session — when
    present, it lets the scoring pipeline skip downloading the recording
    and re-transcribing it with Whisper.

    ``realtime_usage`` is the accumulated token usage for the live
    session — see ``RealtimeUsageDetail``.
    """

    transcript: str | None = None
    realtime_usage: RealtimeUsageDetail | None = None


class InterviewResponse(BaseModel):
    """An interview record — status and, once available, scoring output."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    application_id: uuid.UUID | None
    status: str
    transcript: str | None
    ai_score: int | None
    ai_rationale: str | None
    started_at: datetime | None
    completed_at: datetime | None
    # Surfaced so the consent screen can warn a returning candidate that
    # they've already used their one free restart — see _start_session.
    session_start_count: int


class InterviewDetailResponse(BaseModel):
    """Full interview detail for the employer review UI.

    ``cv_*`` fields are the independently-computed CV fit assessment for
    this same candidate+job pairing (from the application's or talent
    pool profile's own AI scoring), shown alongside the interview
    assessment so the employer can compare the two — not fed into the
    interview scoring prompt itself, to keep the two signals independent.
    """

    model_config = {"from_attributes": True}

    status: str
    transcript: str | None
    ai_score: int | None
    ai_rationale: str | None
    ai_scored_at: datetime | None
    video_url: str | None
    completed_at: datetime | None
    cv_score: int | None = None
    cv_strengths: list[str] | None = None
    cv_weaknesses: list[str] | None = None
    cv_fit_summary: str | None = None


class InterviewPublicInfoResponse(BaseModel):
    """Job/company context shown on the consent screen before an unauthenticated candidate starts."""

    job_title: str
    company_name: str | None
    status: str
    max_duration_minutes: int
    # Surfaced so the consent screen can warn a returning candidate that
    # they've already used their one free restart — see _start_session.
    session_start_count: int


class InterviewResetRequestResponse(BaseModel):
    """Result of a candidate asking the employer to reset their restart lock."""

    sent: bool
    already_requested: bool


class InterviewInviteSendResponse(BaseModel):
    """Result of an explicit single-candidate invite send/resend."""
    sent: bool
    reason: str | None


class InterviewInviteBulkSendResponse(BaseModel):
    """Result of a bulk invite send/resend across a job's interview list."""
    sent: int
    skipped: list[dict]
