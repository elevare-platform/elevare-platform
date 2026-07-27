"""SQLAlchemy ORM model for the per-job interview list."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.jobs.models import Job
    from app.modules.talent_pool.models import TalentPoolProfiles
    from app.modules.users.models import User


class InterviewListEntry(BaseModel):
    """A candidate an employer intends to interview for a specific job.

    Distinct from ``SavedCandidate`` (global, no job) and from
    ``TalentPoolProfiles.status == SHORTLISTED`` (a later pipeline stage,
    the post-interview decision that will eventually trigger a real
    interview invite once AI video interviews exist). This is the
    "queue them up for this role" stage in between.
    """

    __tablename__ = "interview_list_entries"

    __table_args__ = (
        UniqueConstraint(
            "employer_id",
            "talent_pool_profile_id",
            "job_id",
            name="uq_interview_list_entry",
        ),
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    talent_pool_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("talent_pool_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    employer: Mapped[User] = relationship("User", foreign_keys=[employer_id])
    talent_pool_profile: Mapped[TalentPoolProfiles] = relationship(
        "TalentPoolProfiles", foreign_keys=[talent_pool_profile_id]
    )
    job: Mapped[Job] = relationship("Job", foreign_keys=[job_id])
