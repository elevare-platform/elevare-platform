"""Pydantic schemas for job application requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.applications.enums import ApplicationStatus


class ApplicationResponse(BaseModel):
    """Serialised view of a job application returned to the client."""

    id: uuid.UUID
    candidate_id: uuid.UUID
    job_id: uuid.UUID
    status: ApplicationStatus
    cv_id: uuid.UUID | None = Field(default=None, exclude=True)
    cover_letter: str | None = None
    status_updated_at: datetime
    job_title: str | None = None
    job_status: str | None = None
    company_name: str | None = None
    company_logo: str | None = None
    company_industry: str | None = None
    cv_url: str | None = None
    # Candidate details — populated when the employer views applicants
    candidate_name: str | None = None
    candidate_location: str | None = None
    years_of_experience: int | None = None
    candidate_profile_id: uuid.UUID | None = None  # profile PK for employer profile view
    # AI match score — null until background task computes it
    match_score: int | None = None
    score_computed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_application(
        cls, application, cv_url: str | None = None
    ) -> "ApplicationResponse":
        """Build an ApplicationResponse from an Application ORM object.

        cv_url is resolved by the service layer (async presigned URL) and
        passed in here — schemas are synchronous and cannot do async work.
        """
        employer = getattr(application.job, "employer", None)
        employer_profile = getattr(employer, "employer_profile", None) if employer else None

        candidate = getattr(application, "candidate", None)
        candidate_profile = getattr(candidate, "candidate_profile", None) if candidate else None

        candidate_name = None
        if candidate:
            candidate_name = f"{candidate.first_name} {candidate.last_name}".strip()

        return cls(
            id=application.id,
            candidate_id=application.candidate_id,
            job_id=application.job_id,
            status=application.status,
            cv_id=application.cv_id,
            cover_letter=application.cover_letter,
            status_updated_at=application.status_updated_at,
            job_title=application.job.title if application.job else None,
            job_status=application.job.status if application.job else None,
            company_name=employer_profile.company_name if employer_profile else None,
            company_logo=employer_profile.company_logo_url if employer_profile else None,
            company_industry=employer_profile.industry if employer_profile else None,
            cv_url=cv_url,
            candidate_name=candidate_name,
            candidate_location=candidate_profile.location if candidate_profile else None,
            years_of_experience=candidate_profile.years_of_experience if candidate_profile else None,
            candidate_profile_id=candidate_profile.id if candidate_profile else None,
            match_score=application.match_score,
            score_computed_at=application.score_computed_at,
        )


class ApplicationList(BaseModel):
    """Paginated list of applications with cursor for next page."""

    items: list[ApplicationResponse]
    next_cursor: str | None
    count: int
    total: int = 0

class ApplicationFilters(BaseModel):
    """Query filters for listing applications."""

    status: ApplicationStatus | None = None


class ApplicationCreateRequest(BaseModel):
    """Payload for submitting a new job application."""

    job_id: uuid.UUID
    cv_id: uuid.UUID | None = None
    cover_letter: str | None = None


class MyApplicationsRequest(BaseModel):
    """Request body for paginated candidate application listings."""

    filters: ApplicationFilters
    cursor: str
    limit: int


class WithdrawApplication(BaseModel):
    """Payload for withdrawing a specific application."""

    application_id: uuid.UUID


class UpdateApplicationStatus(BaseModel):
    """Payload for updating an application's status."""

    new_status: ApplicationStatus


class HasAppliedBatchRequest(BaseModel):
    """Payload for batch checking whether a candidate has applied to multiple jobs."""

    job_ids: list[uuid.UUID]
