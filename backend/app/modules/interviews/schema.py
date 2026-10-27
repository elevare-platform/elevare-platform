"""Pydantic request and response schemas for the interviews module."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    # The competency of the job's scoring profile this question tests (optional).
    competency: str | None = Field(default=None, max_length=200)
    # The employer's own follow-up probes for this question, one per line (optional). The real
    # limits are checked in ``question_rules``; this only stops an absurdly large request.
    probes: str | None = Field(default=None, max_length=5000)
    # How long the candidate has to answer a follow-up on this question, in seconds (30 to 300).
    # Left out, the platform default (90) applies. The range is checked in ``question_rules``.
    follow_up_seconds: int | None = Field(default=None)
    # True for the interview's practical case: a scenario scored separately out of 5 and never part
    # of the weighted score. At most one question of a job (checked in ``question_rules``).
    is_practical: bool = False


FollowUpModeName = Literal["NONE", "STANDARD", "PROBES_ONLY"]


class InterviewQuestionsPutRequest(BaseModel):
    """The employer's whole list, in the order shown. An empty list clears the questions."""

    questions: list[InterviewQuestionIn] = Field(max_length=50)
    # What the AI may do after an answer, for this job. Left out, the job keeps what it has.
    follow_up_mode: FollowUpModeName | None = None


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
    competency: str | None = None
    probes: str | None = None
    follow_up_seconds: int | None = None
    is_practical: bool = False


class DraftedInterviewQuestion(BaseModel):
    text: str
    time_limit_seconds: int
    source: QuestionSource = "AI"
    competency: str | None = None
    probes: str | None = None
    follow_up_seconds: int | None = None
    is_practical: bool = False


class ClosingQuestion(BaseModel):
    text: str
    time_limit_seconds: int


class QuestionTemplateInfo(BaseModel):
    """A ready-made set of questions an employer can start a job from (the Colton Group roles)."""

    code: str
    title: str
    question_count: int
    total_seconds: int


class QuestionTemplateApplyRequest(BaseModel):
    """Which template to start the job from."""

    code: str = Field(min_length=1, max_length=60)


class _QuestionLimits(BaseModel):
    """What the screen shows next to a list of questions."""

    total_seconds: int
    max_questions: int
    default_questions: int
    max_total_seconds: int
    # The standard closing question the editor offers to add (its text and answer time).
    closing_question: "ClosingQuestion"
    # Which interview new invitations use ("live" or "strict"). The questions editor is only
    # shown when it is "strict".
    style: Literal["live", "strict"]
    # The competencies of the job's scoring profile (for the tag on each question), and which of
    # them no saved question is tagged with. Both empty for a job without a profile.
    competencies: list[str] = []
    untested_competencies: list[str] = []
    # What the AI may do after an answer, for this job: NONE, STANDARD or PROBES_ONLY.
    follow_up_mode: FollowUpModeName = "STANDARD"
    # The ready-made question sets the employer can start from.
    question_templates: list[QuestionTemplateInfo] = []


class InterviewQuestionsResponse(_QuestionLimits):
    questions: list[SavedInterviewQuestion]


class InterviewQuestionsDraftResponse(_QuestionLimits):
    """A draft. Nothing is saved until the employer saves it."""

    questions: list[DraftedInterviewQuestion]


class InterviewQuestionsTemplateResponse(_QuestionLimits):
    """The questions of a template the employer started from. ``saved`` is true when they were
    saved at once; false when their answer times do not fit the interview's time limit, so they
    are only shown, for the employer to shorten and save."""

    questions: list[DraftedInterviewQuestion]
    saved: bool


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
    # What the AI may do after an answer, so the rules the candidate reads say the same.
    follow_up_mode: FollowUpModeName = "STANDARD"


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


class WeightedScoreReport(BaseModel):
    """The weighted score of an interview scored with a scoring profile, as it was when scored.

    ``points`` is earned out of ``assessed_weight`` (the weight of the competencies that were
    rated) and ``total_weight`` is 100. Only when ``complete`` (every competency rated) are
    ``score`` and ``band`` set; otherwise the score is incomplete and a human decides. The band is
    provisional. ``key_flags`` are key competencies rated under ``key_min_rating``."""

    rows: list[dict]
    points: float
    assessed_weight: int
    total_weight: int
    complete: bool
    score: int | None = None
    band: str | None = None
    bands: dict
    key_min_rating: int
    key_flags: list[str] = []
    unassessed: list[str] = []


class PracticalCriterionRow(BaseModel):
    """One criterion of the practical case: its weight, the 1 to 5 rating (None when it was not
    covered) and why."""

    key: str
    name: str
    weight: int
    rating: int | None = None
    rationale: str = ""


class PracticalCaseReport(BaseModel):
    """The practical case of an interview, scored on its own out of 5 and never part of the weighted
    score (docs/08_DECISIONS.md, item 43). ``score`` is set only when every criterion was rated
    (``complete``); otherwise a person decides."""

    question_number: int
    rows: list[PracticalCriterionRow]
    complete: bool
    score: float | None = None
    assessed_weight: int
    total_weight: int
    unassessed: list[str] = []
    summary: str = ""


PanelDecisionName = Literal["STRONG_SHORTLIST", "SHORTLIST", "HOLD", "DO_NOT_SHORTLIST"]


class PanelDecisionIn(BaseModel):
    """The hiring panel's decision about a candidate, and why. The real limits (a rationale of a
    sentence or two) are checked in the service with messages the employer can act on."""

    decision: PanelDecisionName
    rationale: str = Field(max_length=5000)


class PanelDecisionOut(BaseModel):
    """A decision as it was signed off: what, why, by whom and when."""

    decision: PanelDecisionName
    label: str
    rationale: str
    decided_by_name: str
    decided_at: datetime


class AssessmentRecord(BaseModel):
    """The candidate assessment record the client's pack asks for (docs/16_COLTON_BRIEF.md, Section
    7): who and when, how long, the top three strengths and gaps, what to verify and what to ask
    referees, and the human panel's decision with its sign-off. ``panel_decision`` is only on the
    employer's own view: it is the company's internal decision, not part of what a shared link
    shows."""

    reference: str
    role: str
    interview_date: datetime | None = None
    duration_minutes: int | None = None
    interviewer: str
    top_strengths: list[str] = []
    top_gaps: list[str] = []
    claims_to_verify: list[str] = []
    reference_check_questions: list[str] = []
    panel_decision: PanelDecisionOut | None = None


class RecordingClip(BaseModel):
    """One recording of a strict interview: an interview the employer reinstated has one clip
    per attempt, each only what that attempt recorded."""

    attempt: int
    video_url: str


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
    # The latest attempt's recording (the only one, for an interview never reinstated).
    video_url: str | None
    # Every attempt's recording, oldest first. Only more than one clip for a reinstated
    # interview; empty while the latest attempt's pieces are still being joined and there is
    # nothing earlier to show.
    recordings: list[RecordingClip] = []
    completed_at: datetime | None
    cv_score: int | None = None
    cv_strengths: list[str] | None = None
    cv_weaknesses: list[str] | None = None
    cv_fit_summary: str | None = None
    # Only for a strict interview (None for a live one).
    strict: StrictDetail | None = None
    # Only for an interview scored with a scoring profile (None otherwise).
    score_report: WeightedScoreReport | None = None
    # Only for an interview that had a practical case (None otherwise): reported apart from the score.
    practical_case: PracticalCaseReport | None = None
    # The candidate assessment record: header, top strengths and gaps, what to verify, the panel's decision.
    record: AssessmentRecord | None = None


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
    # What the AI may do after an answer, so the rules the candidate reads say the same.
    follow_up_mode: FollowUpModeName = "STANDARD"


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


class InterviewInviteByEmailRequest(BaseModel):
    """An email address to send a job's AI interview to, with no CV and no account needed."""

    email: EmailStr


class InterviewInviteByEmailResponse(InterviewInviteSendResponse):
    """The invite result, plus the candidate's row, which is on the job's interview list
    whether or not the email could be sent (so it can be sent again from there)."""

    talent_pool_profile_id: uuid.UUID


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


class ScoringCompetency(BaseModel):
    """One competency of a scoring profile: its name, its weight (a whole number of percent) and
    whether it is a key competency (rated under the minimum caps the band)."""

    name: str = Field(max_length=200)
    weight: int
    key: bool = False


class ScoringBands(BaseModel):
    """A total at or over ``strong`` is a Strong shortlist, at or over ``shortlist`` a Shortlist,
    at or over ``hold`` Hold for evidence, and under that Do not shortlist."""

    strong: int
    shortlist: int
    hold: int


class ScoringProfileIn(BaseModel):
    """The scoring profile the employer wants to save for a job. Left out, ``bands`` and
    ``key_min_rating`` take the defaults (85, 75, 65 and 3)."""

    competencies: list[ScoringCompetency] = Field(max_length=50)
    bands: ScoringBands | None = None
    key_min_rating: int = 3
    template_code: str | None = Field(default=None, max_length=40)


class ScoringProfileOut(BaseModel):
    competencies: list[ScoringCompetency]
    bands: ScoringBands
    key_min_rating: int
    template_code: str | None = None


class ScoringTemplate(BaseModel):
    """A ready-made profile (the Colton Group's three roles) an employer can start from."""

    code: str
    title: str
    competencies: list[ScoringCompetency]


class ScoringProfileResponse(BaseModel):
    """A job's scoring profile (None when it has none) with the templates and the defaults the
    editor starts from."""

    profile: ScoringProfileOut | None
    templates: list[ScoringTemplate]
    default_bands: ScoringBands
    default_key_min_rating: int
