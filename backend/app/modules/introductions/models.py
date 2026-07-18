"""SQLAlchemy ORM model for introduction requests."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.introductions.enums import IntroductionStatus

if TYPE_CHECKING:
    from app.modules.jobs.models import Job
    from app.modules.talent_pool.models import TalentPoolProfiles
    from app.modules.users.models import User


class IntroductionRequest(BaseModel):
    """
    A candidate introduction request raised by an employer.

    One row per introduction - captures the details of each intro request.
    """

    __tablename__ = "introduction_requests"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    talent_pool_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("talent_pool_profiles.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    status: Mapped[IntroductionStatus] = mapped_column(
        String(20),
        nullable=False,
        default=IntroductionStatus.PENDING.value,
        server_default=IntroductionStatus.PENDING.value,
        index=True,
    )

    token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    employer: Mapped[User] = relationship(
        "User", foreign_keys=[employer_id], back_populates="introduction_requests"
    )
    job: Mapped[Job] = relationship(
        "Job", foreign_keys=[job_id], back_populates="introduction_requests"
    )
    talent_pool_profile: Mapped[TalentPoolProfiles] = relationship(
        "TalentPoolProfiles",
        foreign_keys=[talent_pool_profile_id],
        back_populates="introduction_requests",
    )
