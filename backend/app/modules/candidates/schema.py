"""Pydantic schemas for the candidates module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# ------------------------------------------
#           REQUEST SCHEMAS
# ------------------------------------------

class UpdateProfileSchema(BaseModel):
    """Partial-update payload for a candidate's own profile.

    All fields are optional; only provided fields are written to the database.
    """

    bio: str | None = None
    avatar_url: str | None = None
    skills: list[str] | None = None
    location: str | None = None
    expected_salary: float | None = None
    expected_currency: str | None = None
    years_of_experience: int | None = None
    notice_period_days: int | None = None
    linkedin_url: str | None = None


# ------------------------------------------
#           RESPONSE SCHEMAS
# ------------------------------------------

class CandidateCvsResponse(BaseModel):
    """Response schema for a candidate CV record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    key: str
    filename: str
    is_default: bool
    created_at: datetime
    url: str | None = None  # populated on demand via presigned URL


class CandidateDocumentsResponse(BaseModel):
    """Response schema for a candidate supporting document record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    key: str
    filename: str
    document_type: str | None = None
    created_at: datetime
    url: str | None = None  # populated on demand via presigned URL


class ProfileResponse(BaseModel):
    """Response schema for a full candidate profile, including CVs and documents."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    bio: str | None = None
    avatar_url: str | None = None
    skills: list[str] | None = None
    location: str | None = None
    expected_salary: float | None = None
    expected_currency: str | None = None
    years_of_experience: int | None = None
    notice_period_days: int | None = None
    linkedin_url: str | None = None
    is_profile_complete: bool = False
    cvs: list[CandidateCvsResponse] = []
    documents: list[CandidateDocumentsResponse] = []
