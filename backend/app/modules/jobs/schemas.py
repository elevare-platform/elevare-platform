"""Pydantic request and response schemas for the jobs module."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.jobs.enums import ContractType, SeniorityLevel, WorkLocation, WorkModel

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class JobCreateRequest(BaseModel):
    """Payload for creating a new job listing.

    employer_id and status are set by the service layer — not accepted from
    the client.
    """
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., min_length=10)
    location: str = Field(..., max_length=255)
    contract_type: ContractType
    work_model: WorkModel | None = None
    salary_min: Decimal | None = Field(default=None, ge=0, le=999_999_999_999)
    salary_max: Decimal | None = Field(default=None, ge=0, le=999_999_999_999)
    work_location: WorkLocation
    application_deadline: datetime | None = None
    required_skills: list[str] | None = None
    seniority_level: SeniorityLevel | None = None
    openings_count: int = Field(default=1, ge=1, le=999)
    required_years_experience: int | None = Field(default=None, ge=0, le=50)

    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobCreateRequest":
        """Ensure salary_min does not exceed salary_max when both are provided."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("salary_min cannot be greater than salary_max")
        return self


class JobUpdateRequest(BaseModel):
    """Partial update payload — all fields optional.

    An employer only needs to send the fields they want to change.
    Fields not included in the request are left unchanged.
    """
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, min_length=10)
    location: str | None = Field(default=None, max_length=255)
    contract_type: ContractType | None = None
    work_model: WorkModel | None = None
    salary_min: Decimal | None = Field(default=None, ge=0, le=999_999_999_999)
    salary_max: Decimal | None = Field(default=None, ge=0, le=999_999_999_999)
    work_location: WorkLocation | None = None
    application_deadline: datetime | None = None
    required_skills: list[str] | None = None
    seniority_level: SeniorityLevel | None = None
    openings_count: int | None = Field(default=None, ge=1, le=999)
    required_years_experience: int | None = Field(default=None, ge=0, le=50)


    @model_validator(mode="after")
    def validate_salary_range(self) -> "JobUpdateRequest":
        """Ensure salary_min does not exceed salary_max when both are provided."""
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_min > self.salary_max:
                raise ValueError("salary_min cannot be greater than salary_max")
        return self


# ---------------------------------------------------------------------------
# Query parameter schemas
# ---------------------------------------------------------------------------

class JobFilterParams(BaseModel):
    """Query parameters for the public job listing endpoint."""
    contract_type: ContractType | None = None
    work_model: WorkModel | None = None
    location: str | None = Field(default=None, max_length=255)
    q: str | None = Field(default=None, max_length=255)  # full-text search on title + description
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    work_location: WorkLocation | None = None
    seniority_level: SeniorityLevel | None = None
    min_years_experience: int | None = Field(default=None, ge=0, le=50)
    max_years_experience: int | None = Field(default=None, ge=0, le=50)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class JobResponse(BaseModel):
    """Full job object returned by the API."""
    id: UUID
    title: str
    description: str
    location: str
    contract_type: str
    work_model: str | None
    salary_min: Decimal | None
    salary_max: Decimal | None
    status: str
    employer_id: UUID | None
    company_name: str | None = None
    company_logo_url: str | None = None
    company_website: str | None = None
    company_description: str | None = None
    company_industry: str | None = None
    work_location: WorkLocation
    created_at: datetime | None = None
    application_deadline: datetime | None = None
    application_count: int = 0
    required_skills: list[str] | None = None
    seniority_level: SeniorityLevel | None = None
    openings_count: int = 1
    required_years_experience: int | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_job(cls, job) -> "JobResponse":
        """Build a JobResponse from a Job ORM instance."""
        profile = None
        if job.employer and job.employer.employer_profile:
            profile = job.employer.employer_profile

        return cls(
            id=job.id,
            title=job.title,
            description=job.description,
            location=job.location,
            contract_type=job.contract_type,
            work_model=job.work_model,
            salary_min=job.salary_min,
            salary_max=job.salary_max,
            status=job.status,
            employer_id=job.employer_id,
            work_location=job.work_location,
            company_name=profile.company_name if profile else None,
            company_logo_url=profile.company_logo_url if profile else None,
            company_website=profile.website if profile else None,
            company_description=profile.company_description if profile else None,
            company_industry=profile.industry if profile else None,
            created_at=job.created_at,
            application_deadline=job.application_deadline,
            application_count=getattr(job, "application_count", 0),
            required_skills=job.required_skills,
            seniority_level=job.seniority_level,
            openings_count=job.openings_count,
            required_years_experience=job.required_years_experience,
        )


class JobListResponse(BaseModel):
    """Paginated list of jobs with cursor for next page."""
    items: list[JobResponse]
    next_cursor: str | None
    count: int
    total: int = 0
