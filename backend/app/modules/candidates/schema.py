"""Pydantic schemas for the candidates module."""

from datetime import date, datetime
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
    portfolio_url: str | None = None
    github_url: str | None = None
    preferred_locations: list[str] | None = None
    preferred_work_models: list[str] | None = None
    open_to_relocation: bool = False
    visibility: str | None = None  # PUBLIC | APPLIED_ONLY | PRIVATE


class WorkExperienceCreateSchema(BaseModel):
    """Payload for adding a work experience entry to a candidate's profile."""

    company_name: str
    job_title: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class EducationCreateSchema(BaseModel):
    """Payload for adding an education entry to a candidate's profile."""

    institution_name: str
    degree: str
    field_of_study: str
    start_year: int | None = None
    end_year: int | None = None


class CertificationCreateSchema(BaseModel):
    """Payload for adding a certification to a candidate's profile."""

    name: str
    issuing_organization: str
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = None
    credential_url: str | None = None


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
    cv_parse_status: str = "pending"
    submission_id: UUID | None = None
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


class WorkExperienceResponse(BaseModel):
    """Response schema for a work experience entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    company_name: str
    job_title: str
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool
    created_at: datetime


class EducationResponse(BaseModel):
    """Response schema for an education entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    institution_name: str
    degree: str
    field_of_study: str
    start_year: int | None = None
    end_year: int | None = None
    created_at: datetime


class CertificationResponse(BaseModel):
    """Response schema for a certification entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    candidate_id: UUID
    name: str
    issuing_organization: str
    issue_date: date | None = None
    expiration_date: date | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    created_at: datetime


class ProfileViewResponse(BaseModel):
    """Response schema for a candidate profile view record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    viewed_at: datetime
    company_name: str | None = None
    company_logo_url: str | None = None
    job_title: str | None = None  # populated by the service if job_id is set


class ProfileResponse(BaseModel):
    """Response schema for a full candidate profile, including CVs and documents."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    first_name: str | None = None
    last_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    skills: list[str] | None = None
    location: str | None = None
    expected_salary: float | None = None
    expected_currency: str | None = None
    years_of_experience: int | None = None
    notice_period_days: int | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    preferred_locations: list[str] | None = None
    preferred_work_models: list[str] | None = None
    open_to_relocation: bool = False
    visibility: str = "APPLIED_ONLY"
    is_profile_complete: bool = False
    cvs: list[CandidateCvsResponse] = []
    documents: list[CandidateDocumentsResponse] = []
    work_experiences: list[WorkExperienceResponse] = []
    educations: list[EducationResponse] = []
    certifications: list[CertificationResponse] = []

    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Validate and build the response, enriching name fields from the user relation."""
        instance = super().model_validate(obj, **kwargs)
        # Populate name fields from the user relationship when available
        if hasattr(obj, "user") and obj.user is not None:
            instance.first_name = getattr(obj.user, "first_name", None)
            instance.last_name = getattr(obj.user, "last_name", None)
        return instance
