import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TalentPoolSubmitRequest(BaseModel):
    """Request body for submitting an application to the talent pool."""
    model_config = ConfigDict(
        from_attributes=True
    )

    sourced_for_job_id: uuid.UUID | None = None
    source: str = "email"  # email, referral, linkedin, other
    source_note: str | None = None


class TalentPoolStatusUpdateRequest(BaseModel):
    status: str  # new, shortlisted, archived


class TalentPoolProfileResponse(BaseModel):
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
    message: str
    status: str  # "invite_sent" or "conflict"
    conflict_email: str | None = None  # populated when an active user already exists

