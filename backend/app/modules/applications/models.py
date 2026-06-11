"""SQLAlchemy ORM model for job applications."""

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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

from .enums import ApplicationStatus

if TYPE_CHECKING:
    from app.modules.jobs.models import Job
    from app.modules.users.models import User


class Application(BaseModel):
    """Represents a candidate's application to a job posting."""

    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
        Index("ix_applications_job_id", "job_id"),
        Index("ix_applications_candidate_id", "candidate_id"),
        Index("ix_applications_status", "status"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jobs.id"),
        nullable=False,
    )
    cv_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("candidate_cv.id"),
        nullable=True,
    )
    cover_letter: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=ApplicationStatus.SUBMITTED.value,
        nullable=False,
    )
    status_updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )

    match_score: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )
    score_computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    # Relationships
    job: Mapped[Job] = relationship("Job", foreign_keys=[job_id])
    # candidate_id is a FK to users.id — relationship resolves to the User,
    # from which you can access user.candidate_profile
    candidate: Mapped[User] = relationship(
        "User",
        foreign_keys=[candidate_id],
        back_populates="applications"
    )
    who_updated_status: Mapped[User] = relationship(
        "User",
        foreign_keys=[status_updated_by],
        back_populates="application_updated_by"
    )

