"""Pydantic request and response schemas for the interviews module."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_TRANSCRIPT_CHARS = 150_000

# The questions of a job's strict interview. The real limits (how many, how long, the total) are
# settings and are checked in ``question_rules`` with messages the employer can act on; the
# bounds here only stop an absurdly large request from getting that far.
QuestionSource = Literal["AI", "EMPLOYER"]


class InterviewQuestionIn(BaseModel):
    """One question the employer wants to save, with the seconds to answer it."""

    text: str = Field(max_length=5000)
    time_limit_seconds: int
    source: QuestionSource = "EMPLOYER"


class InterviewQuestionsPutRequest(BaseModel):
    """The employer's whole list, in the order shown. An empty list clears the questions."""

    questions: list[InterviewQuestionIn] = Field(max_length=50)


class InterviewQuestionsDraftRequest(BaseModel):
    """How many questions to draft. Left out, the default (5) is used; never more than the
    most an interview may have."""

    count: int | None = Field(default=None, ge=1, le=50)


class SavedInterviewQuestion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    text: str
    time_limit_seconds: int
    source: QuestionSource


class DraftedInterviewQuestion(BaseModel):
    text: str
    time_limit_seconds: int
    source: QuestionSource = "AI"


class _QuestionLimits(BaseModel):
    """What the screen shows next to a list of questions."""

    total_seconds: int
    max_questions: int
    default_questions: int
    max_total_seconds: int
    # Which interview new invitations use ("live" or "strict"). The questions editor is only
    # shown when it is "strict".
    style: Literal["live", "strict"]


class InterviewQuestionsResponse(_QuestionLimits):
    questions: list[SavedInterviewQuestion]


class InterviewQuestionsDraftResponse(_QuestionLimits):
    """A draft. Nothing is saved until the employer saves it."""

    questions: list[DraftedInterviewQuestion]


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

    # The transcript is typed by the candidate's browser, not by us, and goes
    # straight into the scoring prompt, so its size is bounded. 150k characters
    # is roughly 3 hours of speech; a real interview is a small fraction of it.
    transcript: str | None = Field(default=None, max_length=MAX_TRANSCRIPT_CHARS)
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


class CandidateInterviewResponse(BaseModel):
    """An interview as the CANDIDATE it belongs to may see it: where it stands, never the
    employer's assessment. ``ai_score`` and ``ai_rationale`` are the employer's view of the
    candidate and are left out on purpose (the same rule as ``CandidateApplicationResponse``);
    every candidate-facing interview endpoint must answer with this, not ``InterviewResponse``."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    application_id: uuid.UUID | None
    status: str
    transcript: str | None
    started_at: datetime | None
    completed_at: datetime | None
    session_start_count: int


class CandidateInterviewDetailResponse(CandidateInterviewResponse):
    """The same, as the logged-in candidate's own screen loads it, plus which interview it is
    (the live voice conversation or the strict, text-question one), so the screen opens the
    matching flow."""

    style: Literal["live", "strict"]
    # A strict interview that has been started (so the screen offers "Continue", not the rules).
    started: bool = False


class StrictConductEvent(BaseModel):
    """One row of a strict interview's timeline, with the time the server saw it."""

    kind: str  # LEFT_PAGE | RELOAD | KEY_PRESS | STOPPED | ENDED | REINSTATED
    detail: str | None = None  # the kind of leave, the key, or why it ended
    occurred_at: datetime
    duration_seconds: int | None = None
    attempt: int = 1
    counted: bool = False


class StrictAnswer(BaseModel):
    """One question or follow-up and what the candidate said, as text."""

    number: int
    kind: Literal["QUESTION", "FOLLOW_UP"]
    question: str
    answer: str | None
    answered: bool


class StrictDetail(BaseModel):
    """What an employer (and the shared link) sees about a strict interview, next to the
    recording: the rules the candidate accepted, a conduct summary, the timeline, how it ended,
    and each answer under its question. These are notes for a person to review, never proof,
    and no decision is made from them automatically."""

    rules_version: str | None
    rules_accepted_at: datetime | None
    attempt: int
    # Why the interview ended early (TOO_MANY_LEAVES, TOO_LONG_AWAY, STOPPED), or None.
    ended: str | None
    ended_at: datetime | None
    leaves: int
    away_seconds: int
    key_presses: int
    reloads: int
    # The interview was recorded in pieces (the candidate reloaded, or the employer reinstated
    # it) and the pieces are being joined into one video: the recording shown would be only the
    # last piece, so it is not shown yet. ``recording_partial`` is the same once the joining has
    # had long enough and has evidently failed: the recording shown is then only part of it.
    recording_pending: bool = False
    recording_partial: bool = False
    events: list[StrictConductEvent]
    turns: list[StrictAnswer]


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
    # How the transcript compares with the recording: VERIFIED, MISMATCH
    # (``transcript`` then holds the recording's own transcript, without
    # speaker labels, and the score is based on it), UNAVAILABLE, SERVER_ONLY,
    # or None for interviews that were never checked.
    transcript_check: str | None = None
    ai_score: int | None
    ai_rationale: str | None
    ai_scored_at: datetime | None
    video_url: str | None
    completed_at: datetime | None
    cv_score: int | None = None
    cv_strengths: list[str] | None = None
    cv_weaknesses: list[str] | None = None
    cv_fit_summary: str | None = None
    # Only for a strict interview (None for a live one).
    strict: StrictDetail | None = None


class InterviewPublicInfoResponse(BaseModel):
    """Job/company context shown on the consent screen before an unauthenticated candidate starts."""

    job_title: str
    company_name: str | None
    status: str
    max_duration_minutes: int
    # Surfaced so the consent screen can warn a returning candidate that
    # they've already used their one free restart — see _start_session.
    session_start_count: int
    # Which interview this invitation is: the live voice conversation or the strict,
    # text-question one. Decided when the invite was created; the screen shows the matching flow.
    style: Literal["live", "strict"] = "live"
    # A strict interview that has been started (so the screen offers "Continue", not the rules).
    started: bool = False


class InterviewReinstateResponse(BaseModel):
    """What an employer gets back after reinstating an interview that ended early."""

    status: str
    interview_url: str
    # Whether the candidate was sent the link again by email (not when no address is on file).
    email_sent: bool


class StrictRecordingPartResponse(BaseModel):
    """Where to upload an earlier recording the browser kept across a reload, and which part
    number it is. The server joins the parts with the final recording before scoring."""

    upload_url: str
    expires_in_seconds: int
    part: int


class StrictStartRequest(BaseModel):
    """The candidate starting (or resuming) a strict interview. The first call must carry the
    acceptance of the rules and the version of the rules text the candidate saw."""

    accepted: bool = False
    rules_version: str | None = Field(default=None, max_length=20)


class StrictTurnOut(BaseModel):
    """The question or follow-up on screen now, with the time the SERVER says is left."""

    id: uuid.UUID
    kind: Literal["QUESTION", "FOLLOW_UP"]
    # Which of the job's questions this is (a follow-up carries its question's number).
    number: int
    text: str
    time_limit_seconds: int
    seconds_left: int


class StrictInterviewStateResponse(BaseModel):
    """Where a strict interview stands. ``finished`` means there is no further question: the
    screen stops recording, uploads it and completes the interview as it does today."""

    interview_id: uuid.UUID
    finished: bool
    turn: StrictTurnOut | None
    total_questions: int
    seconds_left_total: int
    max_seconds_total: int
    # Why the interview ended early, or None while it is running. When it is set there is no
    # further question: the screen says so, and sends the recording as it is.
    ended: Literal["TOO_MANY_LEAVES", "TOO_LONG_AWAY", "STOPPED"] | None = None
    # Warnings used so far, against what ends the interview.
    leaves: int = 0
    max_leaves: int = 4
    away_seconds: int = 0
    max_away_seconds: int = 60
    key_presses: int = 0


class StrictEventRequest(BaseModel):
    """One thing the candidate's screen reports during a strict interview: it is still there
    (ping), the page was left (left, with its cause), it is back (returned), or a key that tries
    to leave was pressed (key, with its name). The server times it with its own clock."""

    type: Literal["ping", "left", "returned", "key"]
    cause: Literal["HIDDEN", "BLUR", "FULLSCREEN"] | None = None
    key: str | None = Field(default=None, max_length=40)


class InterviewScoreRequestResponse(BaseModel):
    """Result of asking for a finished interview to be AI-scored."""

    queued: bool


class InterviewResetRequestResponse(BaseModel):
    """Result of a candidate asking the employer to reset their restart lock."""

    sent: bool
    already_requested: bool


class InterviewInviteSendResponse(BaseModel):
    """Result of an explicit single-candidate invite send/resend."""
    sent: bool
    reason: str | None


class InterviewPricingResponse(BaseModel):
    """What an AI interview costs the caller's organization, and what it has left.

    ``charged`` is false when nothing is taken for them: Elevare's own admin
    accounts, an owner with no organization, or a price of 0, and the screen shows
    no cost at all. ``balance`` is the total the organization can spend, made up of
    ``plan_credits`` (included in its plan, replaced at each renewal and spent
    first) and ``purchased_credits`` (bought or granted, never expire).
    ``included_in_plan`` is always false now (a subscriber pays from plan credits
    like everyone else) and only stays so a screen that has not been updated yet
    still reads the response.
    """
    credits_per_interview: int
    balance: int | None
    charged: bool
    included_in_plan: bool = False
    plan_credits: int | None = None
    purchased_credits: int | None = None
    # Which interview new invitations use ("live" or "strict"), so the screen knows whether to
    # offer the strict interview's questions editor.
    style: Literal["live", "strict"] = "live"


class InterviewLinkResponse(BaseModel):
    """The candidate's interview link, for an employer to share themselves."""
    interview_url: str


class InterviewInviteBulkSendResponse(BaseModel):
    """Result of a bulk invite send/resend across a job's interview list."""
    sent: int
    skipped: list[dict]
