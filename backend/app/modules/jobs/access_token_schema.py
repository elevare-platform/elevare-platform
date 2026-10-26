"""Pydantic schemas for job access tokens and public applicant views."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccessTokenResponse(BaseModel):
    """Serialised view of a job access token."""

    id: uuid.UUID
    token: str
    job_id: uuid.UUID
    disclose_names: bool
    show_cv: bool
    expires_at: datetime
    is_active: bool
    revoked_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateAccessTokenRequest(BaseModel):
    """Payload for generating a new job access token."""

    expires_in_days: int = Field(..., ge=1, le=30)
    disclose_names: bool = Field(default=False)
    show_cv: bool = Field(default=False)


class PublicApplicantsItem(BaseModel):
    """Single candidate entry on a public shared view - no auth, name conditional."""

    initials: str
    full_name: str | None = None
    ai_score: int | None = None
    ai_fit_summary: str | None = None
    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    cv_snippet: str | None = None
    cv_download_url: str | None = None
    source: str = "applicant"  # "applicant" (registered) | "external" (uploaded CV)
    # When the application was made / the external CV was added, and when the
    # score was computed. Shown as "Added 3d ago" on the shared page so a new
    # batch stands out in a score-sorted list. Optional: older clients ignore them.
    created_at: datetime | None = None
    ai_score_computed_at: datetime | None = None
    # Which candidates this link's reader has opened (docs/08_DECISIONS.md, item 35). The key is
    # opaque and belongs to this link only; the page sends it back when the reader opens the
    # candidate's details or CV.
    item_key: str | None = None
    is_unseen: bool = False
    # Became visible after the reader's previous visit (never set on a first visit).
    is_new_since_last_visit: bool = False


class PublicApplicantsResponse(BaseModel):
    """Response for a public shared applicant view."""

    job_title: str
    expires_at: datetime
    applicants: list[PublicApplicantsItem]
    # How many the reader has not opened, how many arrived since their previous visit, and when
    # that visit was (None the first time).
    unseen_count: int = 0
    new_since_last_visit_count: int = 0
    previous_visit_at: datetime | None = None


class PublicItemSeenRequest(BaseModel):
    """The reader opened one candidate: the ``item_key`` the page was given for it."""

    item_key: str
