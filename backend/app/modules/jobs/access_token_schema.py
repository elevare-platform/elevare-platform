import uuid
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class AccessTokenResponse(BaseModel):
    id: uuid.UUID
    token: str
    job_id: uuid.UUID
    disclose_names: bool
    expires_at: datetime
    is_active: bool
    revoked_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateAccessTokenRequest(BaseModel):
    expires_in_days: int = Field(..., ge=1, le=30)
    disclose_names: bool = Field(default=False)


class PublicApplicantsItem(BaseModel):
    """Single candidate entry on a public shared view - no auth, name conditional."""
    initials: str
    full_name: str | None = None
    ai_score: int | None = None
    ai_fit_summary: str | None = None
    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    cv_snippet: str | None = None  # First 200 chars of parsed_data.summary, never full CV
class PublicApplicantsResponse(BaseModel):
    job_title: str
    expires_at: datetime
    applicants: list[PublicApplicantsItem]