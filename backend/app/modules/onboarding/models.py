"""SQLAlchemy model for a user's progress through the first-login tour and checklist."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BaseModel

# How the tour ended. No outcome means the user has not seen it yet.
TOUR_COMPLETED = "COMPLETED"
TOUR_SKIPPED = "SKIPPED"

# Checklist steps the server cannot work out from other data, so the app reports them.
# Finishing the company profile, verifying the company and posting a job are worked out
# on the dashboard from data it already has, and are not stored here.
STEP_TALENT_POOL = "talent_pool"
STEP_CANDIDATE_SEARCH = "candidate_search"
STEP_CV_PARSER = "cv_parser"
STEP_INTERVIEW_LIST = "interview_list"
STEP_CREDITS = "credits"
CHECKLIST_STEPS = (
    STEP_TALENT_POOL,
    STEP_CANDIDATE_SEARCH,
    STEP_CV_PARSER,
    STEP_INTERVIEW_LIST,
    STEP_CREDITS,
)


class UserOnboarding(BaseModel):
    """One row per user, made the first time the tour or checklist records something.

    No row means "tour not seen yet", so reading never creates one.
    """

    __tablename__ = "user_onboarding"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_onboarding_user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tour_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tour_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checklist_dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_steps: Mapped[list[str]] = mapped_column(
        ARRAY(String(40)), nullable=False, server_default=text("'{}'")
    )
