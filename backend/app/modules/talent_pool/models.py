"""SQLAlchemy ORM model for talent pool profiles."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import UUID, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.talent_pool.enums import SourceType, TalentPoolStatus

if TYPE_CHECKING:
    from app.modules.ai.models import ParsedCVSubmission
    from app.modules.jobs.models import Job
    from app.modules.applications.models import Application
    from app.modules.users.models import User


class TalentPoolProfiles(BaseModel):
    __tablename__ = "talent_pool_profiles"

    parsed_submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parsed_cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(
        String(20),  # stored as plain string — enum used only for Python-side validation
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
        String(20),  # stored as plain string — enum used only for Python-side validation
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

    # Relationships
    parsed_submission: Mapped["ParsedCVSubmission"] = relationship(
        "ParsedCVSubmission",
        back_populates="talent_pool_profile",  # matches the name on ParsedCVSubmission
    )
    sourced_for_job: Mapped["Job"] = relationship(
        "Job",
        foreign_keys=[sourced_for_job_id],
        back_populates="talent_pool_job",
    )
    promoted_application: Mapped["Application"] = relationship(
        "Application",
        foreign_keys=[promoted_application_id],
        back_populates="promoted_talent_pool_application",
    )
    added_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[added_by],
        back_populates="talent_pool_added_by",
    )
