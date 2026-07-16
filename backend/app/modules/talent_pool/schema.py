"""Pydantic schemas for the talent pool module."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.talent_pool.models import TalentPoolProfiles


class TalentPoolSubmitRequest(BaseModel):
    """Request body for submitting an application to the talent pool."""

    model_config = ConfigDict(from_attributes=True)

    sourced_for_job_id: uuid.UUID | None = None
    source: str = "email"  # email, referral, linkedin, other
    source_note: str | None = None


class TalentPoolStatusUpdateRequest(BaseModel):
    """Payload for updating a talent pool profile's status."""

    status: str  # new, shortlisted, archived


class TalentPoolProfileResponse(BaseModel):
    """Full talent pool profile returned by the API, enriched with parsed CV data."""

    id: uuid.UUID
    parsed_submission_id: uuid.UUID | None = None
    candidate_profile_id: uuid.UUID | None = None
    source: str
    source_note: str | None = None
    sourced_for_job_id: uuid.UUID | None = None
    added_by: uuid.UUID
    status: str
    promoted_application_id: uuid.UUID | None = None
    promoted_at: datetime | None = None
    last_invite_sent_at: datetime | None = None
    created_at: datetime

    # Enriched from parsed_data — not stored on the model, populated by the service
    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_current_title: str | None = None

    ai_score: int | None = None
    ai_fit_summary: str | None = None
    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    ai_score_computed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TalentPoolPromoteResponse(BaseModel):
    """Response after a talent pool promotion attempt."""

    message: str
    status: str  # "invite_sent" or "conflict"
    conflict_email: str | None = None  # populated when an active user already exists


class TalentMatchResponse(BaseModel):
    """Single AI-matched talent pool profile returned to the employer."""

    model_config = ConfigDict(from_attributes=True)

    profile_id: uuid.UUID
    similarity_score: int
    candidate_name: str | None = None
    current_title: str | None = None
    profession: str | None = None
    years_of_experience: int | None = None
    location: str | None = None
    top_skills: list[str] = []

    @classmethod
    def from_match(
        cls,
        profile: "TalentPoolProfiles",
        distance: float,
        candidate_name: str | None = None,
        current_title: str | None = None,
        profession: str | None = None,
        years_of_experience: int | None = None,
        location: str | None = None,
        top_skills: list[str] | None = None,
    ) -> "TalentMatchResponse":
        """Build from a repository result with pre-resolved fields."""
        return cls(
            profile_id=profile.id,
            similarity_score=max(0, min(100, round((1 - distance) * 100))),
            candidate_name=candidate_name,
            current_title=current_title,
            profession=profession,
            years_of_experience=years_of_experience,
            location=location,
            top_skills=top_skills or [],
        )


class TalentMatchListResponse(BaseModel):
    items: list[TalentMatchResponse]
    count: int
    job_id: uuid.UUID
