"""SQLAlchemy ORM model for talent pool profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import UUID, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.talent_pool.enums import SourceType, TalentPoolStatus

if TYPE_CHECKING:
    from app.modules.ai.models import ParsedCVSubmission
    from app.modules.applications.models import Application
    from app.modules.candidates.models import CandidateProfile
    from app.modules.jobs.models import Job
    from app.modules.users.models import User


class TalentPoolProfiles(BaseModel):
    """A talent pipeline entry — either a sourced external CV or a self-registered candidate."""

    __tablename__ = "talent_pool_profiles"

    parsed_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parsed_cv_submissions.id", ondelete="CASCADE"),
        nullable=True,  # null for self-registered candidates who have no CV submission
    )
    # Links self-registered candidates back to their structured profile
    # Unique — one pool entry per candidate profile, ever
    candidate_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    source: Mapped[str] = mapped_column(
        String(
            20
        ),  # stored as plain string — enum used only for Python-side validation
        nullable=False,
        index=True,
        default=SourceType.OTHER.value,
        server_default=SourceType.OTHER.value,
    )
    source_note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sourced_for_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    added_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(
            20
        ),  # stored as plain string — enum used only for Python-side validation
        nullable=False,
        index=True,
        default=TalentPoolStatus.NEW.value,
        server_default=TalentPoolStatus.NEW.value,
    )
    # unique=True enforces one talent pool profile → one application, ever
    promoted_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    # tracks when the most recent invite was sent during promotion flow
    last_invite_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ai_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    ai_strengths: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_weaknesses: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    ai_fit_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    ai_score_job_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    ai_score_cv_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    ai_score_computed_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )

    # Embedding columns — generated from parsed CV data
    profile_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True
    )
    embedding_source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    parsed_submission: Mapped[ParsedCVSubmission | None] = relationship(
        "ParsedCVSubmission",
        back_populates="talent_pool_profile",
    )
    candidate_profile: Mapped[CandidateProfile | None] = relationship(
        "CandidateProfile",
        foreign_keys=[candidate_profile_id],
        back_populates="talent_pool_profile",
    )
    sourced_for_job: Mapped[Job] = relationship(
        "Job",
        foreign_keys=[sourced_for_job_id],
        back_populates="talent_pool_job",
    )
    promoted_application: Mapped[Application] = relationship(
        "Application",
        foreign_keys=[promoted_application_id],
        back_populates="promoted_talent_pool_application",
    )
    added_by_user: Mapped[User] = relationship(
        "User",
        foreign_keys=[added_by],
        back_populates="talent_pool_added_by",
    )
