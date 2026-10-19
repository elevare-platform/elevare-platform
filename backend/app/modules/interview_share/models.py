"""SQLAlchemy model for a shareable, read-only link to a job's interview results."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BaseModel


class InterviewShareLink(BaseModel):
    """A link that shows one job's interview results to anyone who has it.

    Meant for a client who is not going to learn the platform: they open the link and
    see each candidate's interview and CV assessment, the recording and the transcript.
    It needs no login, so it expires, can be revoked, and there is at most ONE active
    link per job (a partial unique index, so two people pressing "Share" at once cannot
    create two live links).
    """

    __tablename__ = "interview_share_links"
    __table_args__ = (
        Index(
            "uq_interview_share_one_active_per_job",
            "job_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    view_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
