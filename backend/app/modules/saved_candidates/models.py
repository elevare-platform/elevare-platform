"""SQLAlchemy ORM model for employer-saved candidates."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.talent_pool.models import TalentPoolProfiles
    from app.modules.users.models import User


class SavedCandidate(BaseModel):
    """An employer's bookmark on a candidate — global, not tied to any job.

    Distinct from both ``TalentPoolProfiles.status == SHORTLISTED`` (a later
    pipeline stage, post-interview) and the per-job Interview List — this is
    the lightweight "I noticed this person" heart, available the moment a
    candidate is found anywhere (search, AI matches, applicants).
    """

    __tablename__ = "saved_candidates"

    __table_args__ = (
        UniqueConstraint(
            "employer_id", "talent_pool_profile_id", name="uq_saved_candidate"
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
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    employer: Mapped[User] = relationship("User", foreign_keys=[employer_id])
    talent_pool_profile: Mapped[TalentPoolProfiles] = relationship(
        "TalentPoolProfiles", foreign_keys=[talent_pool_profile_id]
    )
