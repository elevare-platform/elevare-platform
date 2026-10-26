"""Which CVs someone has already looked at (docs/08_DECISIONS.md, item 35).

Two places need it, and they work the same way:

* the employer's Talent Pool page: a CV is NEW until the employer opens it;
* the shared link a company sends to an outside reader: each link remembers what was opened and
  when it was last visited, so a reader coming back a week later is shown what is new.

Everything here is additive: four new tables, nothing changed in the tables they point to.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BaseModel


class EmployerSeenBaseline(BaseModel):
    """The moment an employer first used the "new" markers. A CV added before it is never shown
    as new to that employer: without this, switching the feature on would mark every CV they
    already had as new."""

    __tablename__ = "employer_seen_baselines"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    baseline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TalentPoolProfileView(BaseModel):
    """An employer opened this talent pool CV. One row per employer and CV, ever."""

    __tablename__ = "talent_pool_profile_views"
    __table_args__ = (
        UniqueConstraint("employer_id", "talent_pool_profile_id", name="uq_talent_pool_profile_view"),
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    talent_pool_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("talent_pool_profiles.id", ondelete="CASCADE"), nullable=False
    )
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SharedLinkVisit(BaseModel):
    """When a shared link was last opened, and the visit before it, so the page can say what was
    added since the reader was last here. One row per link."""

    __tablename__ = "job_access_token_visits"

    token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_access_tokens.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    previous_visit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_visit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SharedLinkItemView(BaseModel):
    """A reader of a shared link opened this candidate (its details or its CV). The candidate is
    named by an opaque key made from the link and the candidate, never by the candidate's own id."""

    __tablename__ = "job_access_token_item_views"
    __table_args__ = (UniqueConstraint("token_id", "item_key", name="uq_shared_link_item_view"),)

    token_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_access_tokens.id", ondelete="CASCADE"), nullable=False
    )
    item_key: Mapped[str] = mapped_column(String(16), nullable=False)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
