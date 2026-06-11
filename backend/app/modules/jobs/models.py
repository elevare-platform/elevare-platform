"""SQLAlchemy ORM model for job listings."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    UUID,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

from .enums import (
    ContractType,
    JobStatus,
    ModerationStatus,
    SeniorityLevel,
    WorkLocation,
    WorkModel,
)

if TYPE_CHECKING:
    from app.modules.applications.models import Application
    from app.modules.users.models import User


class Job(BaseModel):
    """A job listing posted by an employer."""

    __tablename__ = "jobs"

    __table_args__ = (
        Index('ix_job_status_created_at', 'status', 'created_at'),
        Index('ix_jobs_employer_id', 'employer_id'),
        Index("ix_jobs_work_model", "work_model"),
        Index("ix_jobs_location", "location"),
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    salary_min: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True
    )
    salary_max: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=True
    )
    status: Mapped[JobStatus] = mapped_column(
        String(20),
        default=JobStatus.DRAFT,
        nullable=False
    )
    work_model: Mapped[WorkModel] = mapped_column(
        String(20),
        nullable=True
    )
    contract_type: Mapped[ContractType] = mapped_column(
        String(20),
        nullable=False
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    work_location: Mapped[WorkLocation] = mapped_column(
        String(20),
        nullable=False,
        default=WorkLocation.LOCAL.value,
        server_default=WorkLocation.LOCAL.value,
        index=True,
    )
    application_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True
    )

    required_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    seniority_level: Mapped[SeniorityLevel | None] = mapped_column(String(20), nullable=True)
    openings_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False, server_default="1")
    required_years_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)

    moderation_status: Mapped[ModerationStatus] = mapped_column(
        String(20),
        nullable=False,
        server_default=ModerationStatus.PENDING.value,
        default=ModerationStatus.PENDING.value,
    )


    # relationship
    employer: Mapped[User] = relationship(
        "User",
        back_populates="jobs",
        foreign_keys=[employer_id],
    )
    applications: Mapped[list[Application]] = relationship(
        "Application",
        back_populates="job"
    )



