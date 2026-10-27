"""SQLAlchemy ORM model for AI video interviews."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

from .enums import InterviewStatus

if TYPE_CHECKING:
    from app.modules.applications.models import Application
    from app.modules.jobs.models import Job
    from app.modules.talent_pool.models import TalentPoolProfiles


class JobInterviewQuestion(BaseModel):
    """One question of a job's strict interview, with the time a candidate has to answer it.

    A job has one list, in ``position`` order, the same for every candidate (decision: the
    questions are made once per job, so candidates can be compared fairly). The AI drafts
    the list from the job's interview brief and the employer edits it; ``source`` says who
    wrote each question. Replacing the list deletes and re-adds the rows in one transaction.
    """

    __tablename__ = "job_interview_questions"
    __table_args__ = (
        UniqueConstraint("job_id", "position", name="uq_job_interview_questions_position"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # 1, 2, 3 ... the order the candidate sees them.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # How long the candidate has to answer this question (a follow-up gets its own,
    # shorter allowance on top). Set by the AI when it drafts, and changeable by the employer.
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    # "AI" (drafted) or "EMPLOYER" (written or edited by the employer).
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="EMPLOYER")
    # The competency of the job's scoring profile this question was written to test, or None
    # (optional). Used to warn when a weighted competency has no question, and told to the scorer.
    competency: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # The employer's own follow-up probes for this question, one per line (docs/08_DECISIONS.md,
    # item 40). Used according to the job's follow-up mode. None when there are none.
    probes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # How long the candidate has to answer a follow-up on this question (docs/08_DECISIONS.md, item
    # 41). None means the platform's default (`strict_follow_up_seconds`, 90).
    follow_up_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The practical case of the interview (docs/08_DECISIONS.md, item 43): a realistic scenario the
    # candidate works through aloud, scored separately out of 5 and never added to the weighted
    # score. At most one question of a job is the practical case.
    is_practical: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False, server_default=sa.false()
    )


class JobInterviewSettings(BaseModel):
    """How a job's strict interview behaves, beyond its questions (docs/08_DECISIONS.md, item 40).
    One row per job; a job without one uses the standard behaviour. A table of its own, not
    columns on ``jobs``, so the live jobs schema is untouched (migration p22_0034)."""

    __tablename__ = "job_interview_settings"
    __table_args__ = (UniqueConstraint("job_id", name="uq_job_interview_settings_job"),)

    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NONE, STANDARD or PROBES_ONLY (enums.FollowUpMode).
    follow_up_mode: Mapped[str] = mapped_column(String(12), nullable=False, default="STANDARD")


class InterviewQuestionTemplate(BaseModel):
    """A set of interview questions a company saved to use again (docs/08_DECISIONS.md, item 46):
    the questions with their probes, times and practical case, the follow-up choice, and, if the
    employer chose to include it, the scoring profile the question tags point to. Owned by the
    company (decision D2), not by the person who saved it: anyone in the company can use it. A table
    of its own, so nothing existing is touched (migration p22_0038)."""

    __tablename__ = "interview_question_templates"
    __table_args__ = (
        sa.Index(
            "uq_interview_question_templates_org_name",
            "organization_id",
            sa.text("lower(name)"),
            unique=True,
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # [{"text", "time_limit_seconds", "competency", "probes", "follow_up_seconds", "is_practical"}, ...]
    questions: Mapped[list] = mapped_column(JSONB, nullable=False)
    # {"competencies", "bands", "key_min_rating"} or None when the set was saved without one.
    scoring_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    follow_up_mode: Mapped[str] = mapped_column(String(12), nullable=False, default="STANDARD")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Kept as a name too, so the library still reads if the account is removed.
    created_by_name: Mapped[str] = mapped_column(String(200), nullable=False)


class JobScoringProfile(BaseModel):
    """A job's scoring profile (docs/08_DECISIONS.md, item 36): the competencies the strict
    interview rates, each with a weight (the weights add up to 100), which of them are "key", and
    the thresholds of the suggested bands. One row per job; a job without one is scored by the
    generic scorecard. Kept in a table of its own, not as a column on ``jobs``, so adding it never
    touches the live jobs schema (see migration p22_0033)."""

    __tablename__ = "job_scoring_profiles"

    job_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    # [{"name": str, "weight": int, "key": bool}, ...] in the order the employer set them.
    competencies: Mapped[list] = mapped_column(JSONB, nullable=False)
    # {"strong": 85, "shortlist": 75, "hold": 65}: a total at or over a threshold gets that band.
    bands: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # A key competency rated under this caps the band at "Hold for evidence".
    key_min_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    # Which template it was started from (None: written by the employer), for the editor.
    template_code: Mapped[str | None] = mapped_column(String(40), nullable=True)


class InterviewWeightedScore(BaseModel):
    """The weighted score report of one interview scored with a scoring profile: the rows with
    their ratings, the points, whether it is complete, the band and the key flags, as they were
    when it was scored (a later edit of the profile never changes a past report). One row per
    interview. A new table, so the interviews table is untouched."""

    __tablename__ = "interview_weighted_scores"

    interview_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    report: Mapped[dict] = mapped_column(JSONB, nullable=False)


class InterviewPanelDecision(BaseModel):
    """The hiring panel's own decision about a candidate after an interview, with its rationale and
    who signed it off (docs/08_DECISIONS.md, item 44; the client's assessment record). A human
    decision, never the system's: the options stop at the shortlist, because hiring is outside the
    platform's scope. Append-only: recording a decision again adds a row, and the latest is the one
    shown, so what was decided before is kept."""

    __tablename__ = "interview_panel_decisions"
    __table_args__ = (sa.Index("ix_interview_panel_decisions_interview", "interview_id", "decided_at"),)

    interview_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    # STRONG_SHORTLIST, SHORTLIST, HOLD or DO_NOT_SHORTLIST (enums.PanelDecision).
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # Who signed it off. Kept as a name too, so the record still reads if the account is removed.
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StrictInterviewRun(BaseModel):
    """The state of one interview that uses the strict, text-question style.

    Having a row is what makes an interview strict: the style is decided when the invite is
    created and an interview with no row is the existing live interview. Kept in its own
    table, not as columns on ``Interview``, so adding it never touches the live interview
    schema (see migration p22_0030).

    ``questions`` is a copy of the job's questions taken when the interview starts: the
    employer editing the list afterwards never changes an interview that has begun.
    """

    __tablename__ = "interview_strict_runs"
    __table_args__ = (
        UniqueConstraint("interview_id", name="uq_interview_strict_runs_interview"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The version of the rules text the candidate saw when they accepted it, and when.
    rules_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rules_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # [{"text": ..., "time_limit_seconds": ..., "competency": ..., "probes": ...}, ...] in the order
    # asked. None until started.
    questions: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # The job's follow-up mode, copied when the interview starts (like the questions) so an edit
    # made later never changes an interview that has begun. None for a run started before the
    # mode existed, which is the standard.
    follow_up_mode: Mapped[str | None] = mapped_column(String(12), nullable=True)
    # When the interview's own clock began. The whole interview ends this long after.
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Earlier recordings that survived a reload and were uploaded as separate parts
    # (interviews/<id>/part-<n>.webm). Joined into one video before scoring, then back to 0.
    recording_parts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    # Which try this is; an employer reinstating an ended interview starts the next one. The
    # leave count and the time away are counted per attempt.
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    # The last time the candidate's screen was heard from (a heartbeat every 15 seconds).
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set while the candidate is away from the interview screen: when it began and why.
    away_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    away_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # When the interview was ended or stopped, and why (an ``END_*`` value). Cleared when it is
    # reinstated; the timeline keeps the history.
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Set when an employer reinstates an interview: the moment its clock stopped. The clock
    # starts again when the candidate next opens the link, which moves the interview's start and
    # the open question forward by the time in between. Cleared then.
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The final recordings of earlier attempts (storage keys, oldest first). They are joined in
    # front of the latest one when the interview finishes.
    previous_recordings: Mapped[list | None] = mapped_column(JSONB, nullable=True)


class InterviewConductEvent(BaseModel):
    """One row of a strict interview's timeline: a leave, a reload, a key press, a stop, an
    ending or a reinstatement, with the time the SERVER saw it (so the employer can check it
    against the recording). Kept after the interview, with the recording."""

    __tablename__ = "interview_conduct_events"
    __table_args__ = (Index("ix_interview_conduct_events_interview_id", "interview_id"),)

    interview_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    # A ConductEventKind value.
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # What kind of leave (HIDDEN, BLUR, FULLSCREEN), which key, or why it ended.
    detail: Mapped[str | None] = mapped_column(String(40), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # How long a leave or reload lasted; None for a leave still open and for other kinds.
    duration_seconds: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    # Whether it counts towards ending the interview (a key press never does).
    counted: Mapped[bool] = mapped_column(
        sa.Boolean, default=False, server_default=sa.false(), nullable=False
    )


class InterviewTurn(BaseModel):
    """One question or follow-up the candidate was shown, and what they said.

    The server opens one turn at a time and records when it was shown, so the time left is
    the server's, not the browser's. Only the text of the answer is kept here (the whole
    interview is recorded as one video). ``answer_text`` stays empty when the answer could
    not be transcribed; the recording still has it.
    """

    __tablename__ = "interview_turns"
    __table_args__ = (
        UniqueConstraint("interview_id", "position", name="uq_interview_turns_position"),
        Index("ix_interview_turns_interview_id", "interview_id"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 1, 2, 3 ... the order shown, follow-ups included.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # A TurnKind value.
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    # Which of the job's questions this turn belongs to (a follow-up shares its question's).
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_seconds: Mapped[float | None] = mapped_column(sa.Float, nullable=True)


class Interview(BaseModel):
    """A candidate's live AI video interview for one job.

    Keyed by (job_id, talent_pool_profile_id) — the same identity
    InterviewListEntry uses — not by application_id. Being on a job's
    interview list is what grants access to the interview, and a
    candidate can be added to that list whether or not they ever
    submitted a formal Application (e.g. sourced/parsed profiles the
    employer reaches out to directly). application_id is populated
    best-effort, only when a matching Application happens to exist, so
    the logged-in candidate dashboard can link to it — it is never the
    access-control key.

    ``token`` lets a candidate with no Elevare account (a parsed/sourced
    profile) start the interview from an emailed link with no login,
    the same pattern used by IntroductionRequest.
    """

    __tablename__ = "interviews"

    __table_args__ = (
        UniqueConstraint(
            "job_id", "talent_pool_profile_id", name="uq_interviews_job_profile"
        ),
        Index("ix_interviews_status", "status"),
        Index("ix_interviews_token", "token", unique=True),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id"),
        nullable=False,
    )
    talent_pool_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("talent_pool_profiles.id"),
        nullable=False,
    )
    # Best-effort link to a real Application, when one exists — never the
    # access-control key, see class docstring.
    application_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("applications.id"),
        nullable=True,
    )

    token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=InterviewStatus.PENDING.value,
        server_default=InterviewStatus.PENDING.value,
        nullable=False,
    )

    # R2 object key for the candidate's recorded video, set once upload completes.
    r2_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)

    ai_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_scored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Counts how many times a live Realtime session has actually been
    # minted for this interview (not how many times the page was viewed).
    # Each session is a fresh conversation with the AI interviewer, so a
    # candidate who reloads mid-interview gets to hear the opening
    # question again with a running start — one reload is tolerated (a
    # genuine crash/dropped connection), a second is treated as gaming
    # the interview and blocked. See _start_session.
    session_start_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    # Set when a candidate locked out by the restart lock asks the
    # employer to reset it (see InterviewService._request_reset). Kept
    # non-null until the employer actually resends the invite
    # (create_invite clears it), so the candidate can't spam the employer
    # with repeat notifications by re-hitting the request endpoint.
    reset_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Video retention — 90 days from upload by default (see
    # docs/ai-video-interview-self-built-proposal.md). A background task
    # deletes the R2 object and nulls r2_key once this passes.
    video_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    job: Mapped[Job] = relationship("Job", foreign_keys=[job_id])
    talent_pool_profile: Mapped[TalentPoolProfiles] = relationship(
        "TalentPoolProfiles", foreign_keys=[talent_pool_profile_id]
    )
    application: Mapped[Application | None] = relationship(
        "Application", foreign_keys=[application_id]
    )


class InterviewTranscriptCheck(BaseModel):
    """Server-side verification of an interview's candidate-device transcript.

    The transcript the scoring step reads is assembled in the candidate's
    browser, so it cannot be trusted on its own. After the interview we
    transcribe the recording ourselves and compare the two; this row keeps
    that second transcript and the outcome. Kept in its own table, not as
    columns on ``Interview``, so the bulky text stays out of every interview
    query and the table can be added without touching the live interview schema.
    """

    __tablename__ = "interview_transcript_checks"

    __table_args__ = (
        UniqueConstraint("interview_id", name="uq_interview_transcript_checks_interview"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    # A TranscriptCheckStatus value.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Share of the submitted transcript's word pairs found in the recording's
    # own transcript, 0.0 to 1.0. None when no comparison could be made.
    match_score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    server_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)


class InterviewCost(BaseModel):
    """Records the billed cost of one external API call tied to an interview.

    One interview typically produces up to 3 rows — realtime (the live
    voice session), transcription (Whisper, fallback-only, only written
    when there was no client-captured transcript), and scoring (Claude).
    The three components bill in different units (tokens vs. audio
    duration vs. tokens-with-audio/text/cached breakdown), so unit-specific
    columns are nullable rather than forcing one shape on all of them.
    ``usage_detail`` keeps the raw usage payload as received, so cost can
    be recomputed later if the pricing table in app/core/ai_pricing.py
    changes.
    """

    __tablename__ = "interview_costs"

    __table_args__ = (
        Index("ix_interview_costs_interview_id", "interview_id"),
        Index("ix_interview_costs_created_at", "created_at"),
        Index("ix_interview_costs_component", "component"),
    )

    interview_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    component: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(
        sa.Numeric(10, 2), nullable=True
    )
    usage_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Nullable for the same reason as CVParsingCost.cost_usd — a model
    # missing from the pricing table still gets a row with real usage
    # data and cost_usd=NULL, not a wrong $0 or a dropped row.
    cost_usd: Mapped[float | None] = mapped_column(sa.Numeric(10, 6), nullable=True)

    interview: Mapped[Interview] = relationship(
        "Interview", foreign_keys=[interview_id]
    )
