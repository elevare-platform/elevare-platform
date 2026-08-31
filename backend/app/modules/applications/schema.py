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
    candidate_profile_id: uuid.UUID | None = (
        None  # profile PK for employer profile view
    )
    # AI match score — null until background task computes it
    match_score: int | None = None
    score_computed_at: datetime | None = None
    # True when the job has an AI video interview configured AND the
    # employer has added this candidate to the job's interview list —
    # drives whether the candidate sees a "Start AI Interview" action.
    # Being on the interview list is the actual invite; a job merely
    # having a brief is not enough on its own.
    has_ai_interview: bool = False
    # Real Interview.status (PENDING/IN_PROGRESS/UPLOADED/SCORED/FAILED/
    # EXPIRED), or null if never invited — lets the frontend tell "not
    # started" apart from "already completed", which has_ai_interview
    # alone can't (it only reflects invite-list membership).
    interview_status: str | None = None
    # Phase 11.5 composite AI score — distinct from match_score (Phase 6.5 keyword signal)
    ai_score: int | None = None
    ai_fit_summary: str | None = None
    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    ai_score_computed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_application(
        cls,
        application,
        cv_url: str | None = None,
        interview_invited: bool = False,
        interview_status: str | None = None,
    ) -> "ApplicationResponse":
        """Build an ApplicationResponse from an Application ORM object.

        cv_url, interview_invited, and interview_status are resolved by
        the service layer (async presigned URL / interview-list
        membership / Interview.status lookup) and passed in here —
        schemas are synchronous and cannot do async work.
        """
        employer = getattr(application.job, "employer", None)
        employer_profile = (
            getattr(employer, "organization", None) if employer else None
        )

        candidate = getattr(application, "candidate", None)
        candidate_profile = (
            getattr(candidate, "candidate_profile", None) if candidate else None
        )

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
            company_logo=(
                employer_profile.company_logo_url if employer_profile else None
            ),
            company_industry=employer_profile.industry if employer_profile else None,
            cv_url=cv_url,
            candidate_name=candidate_name,
            candidate_location=(
                candidate_profile.location if candidate_profile else None
            ),
            years_of_experience=(
                candidate_profile.years_of_experience if candidate_profile else None
            ),
            candidate_profile_id=candidate_profile.id if candidate_profile else None,
            has_ai_interview=bool(
                application.job and application.job.interview_brief
            )
            and interview_invited,
            interview_status=interview_status,
            match_score=application.match_score,
            score_computed_at=application.score_computed_at,
            ai_score=application.ai_score,
            ai_fit_summary=application.ai_fit_summary,
            ai_strengths=application.ai_strengths,
            ai_weaknesses=application.ai_weaknesses,
            ai_score_computed_at=application.ai_score_computed_at,
        )


class CandidateApplicationResponse(ApplicationResponse):
    """Candidate-facing view of an application — AI scoring fields are excluded.

    Inherits all fields from ApplicationResponse but strips AI fields from
    serialised output so candidates never see scoring data.
    """

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_application(
        cls, application, cv_url: str | None = None, interview_invited: bool = False
    ) -> "CandidateApplicationResponse":
        instance = super().from_application(
            application, cv_url=cv_url, interview_invited=interview_invited
        )
        # Null out AI fields so they are omitted from candidate-facing responses
        instance.ai_score = None
        instance.ai_fit_summary = None
        instance.ai_strengths = None
        instance.ai_weaknesses = None
        instance.ai_score_computed_at = None
        instance.match_score = None
        instance.score_computed_at = None
        return instance


class ApplicationList(BaseModel):
    """Paginated list of applications with cursor for next page."""

    items: list[ApplicationResponse]
    next_cursor: str | None
    count: int
    total: int = 0


class CandidateApplicationList(BaseModel):
    """Candidate-facing paginated list — AI score fields excluded from items."""

    items: list[CandidateApplicationResponse]
    next_cursor: str | None
    count: int
    total: int = 0


class ApplicationFilters(BaseModel):
    """Query filters for listing applications."""

    status: ApplicationStatus | None = None
    sort: str | None = (
        None  # "ai_score" → descending by ai_score; default is created_at desc
    )


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
