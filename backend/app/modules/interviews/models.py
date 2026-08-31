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
