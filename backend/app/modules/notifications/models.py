"""SQLAlchemy ORM model for the generic notifications table."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.candidates.models import CandidateProfile
    from app.modules.jobs.models import Job
    from app.modules.talent_pool.models import TalentPoolProfiles
    from app.modules.users.models import User


class Notification(BaseModel):
    """A generic in-app notification for any user.

    Designed to serve match alerts, email confirmations, and any future
    notification type without schema changes — ``type`` is the discriminator,
    ``entity_type`` / ``entity_id`` carry the optional linked resource.
    """

    __tablename__ = "notifications"

    __table_args__ = (
        Index("ix_notifications_recipient_id", "recipient_id"),
        Index("ix_notifications_read_at", "read_at"),
        Index("ix_notifications_type", "type"),
    )

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # e.g. "NEW_JOB_MATCHES" | "NEW_CANDIDATE_MATCHES" | "APPLICATION_STATUS" …
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional link-back: e.g. entity_type="JOB", entity_id=<job uuid>
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    recipient: Mapped[User] = relationship("User", back_populates="notifications")


class MatchNotification(BaseModel):
    __tablename__ = "match_notifications"

    __table_args__ = (
        Index("ix_match_notifications_job_id", "job_id"),
        Index("ix_match_notifications_is_new", "job_id", "is_new"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    candidate_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=True,
    )
    talent_pool_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("talent_pool_profiles.id", ondelete="CASCADE"),
        nullable=True,
    )
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_new: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa.text("true")
    )
    viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    job: Mapped[Job] = relationship("Job", back_populates="match_notifications")
    candidate_profile: Mapped[CandidateProfile | None] = relationship(
        "CandidateProfile",
        back_populates="match_notifications",
        foreign_keys=[candidate_profile_id],
    )
    talent_pool_profile: Mapped[TalentPoolProfiles | None] = relationship(
        "TalentPoolProfiles",
        back_populates="match_notifications",
        foreign_keys=[talent_pool_profile_id],
    )
