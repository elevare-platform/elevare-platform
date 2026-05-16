"""SQLAlchemy ORM model for job listings."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

from .enums import ContractType, JobStatus, WorkLocation, WorkModel

if TYPE_CHECKING:
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
    title: Mapped[str] = mapped_column(String(50), nullable=False)
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

    # relationship
    employer: Mapped[User] = relationship("User", back_populates="jobs")


