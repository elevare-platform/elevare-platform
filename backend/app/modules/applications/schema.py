"""Pydantic schemas for job application requests and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.applications.enums import ApplicationStatus
from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME


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
    # True until the employer opens this applicant (CV, profile or cover letter), for an
    # application made after they first used the markers (docs/08_DECISIONS.md, item 35).
    # Only set on the employer's list of a job's applicants.
    is_new: bool = False
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
    # Why there is no score: "CV_UNREADABLE" or "SCORING_FAILED"; None otherwise.
    ai_score_failure: str | None = None

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
        if employer_profile and employer_profile.company_name:
            company_name = employer_profile.company_name
        elif employer and getattr(employer, "role", None) == "ADMIN":
            company_name = PLATFORM_COMPANY_NAME
        else:
            company_name = None

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
            company_name=company_name,
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
            # A job's interview exists when it has a brief or, for the strict interview, questions
            # only; an interview row for this candidate (its status) proves the second.
            has_ai_interview=bool(
                (application.job and application.job.interview_brief) or interview_status
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
            ai_score_failure=application.ai_score_failure,
        )


class CandidateApplicationResponse(ApplicationResponse):
    """Candidate-facing view of an application — AI scoring fields are excluded.

    Inherits all fields from ApplicationResponse but strips the scoring data so
    candidates never see it.

    The stripping is a validator, so it runs however an instance comes about.
    It used to live in an overridden ``from_application`` that the candidate
    endpoints never called: they return plain ``ApplicationResponse`` objects and
    let the response model convert them, which skipped the override and sent the
    employer-only AI score, summary, strengths and match score to the candidate.
    """

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _strip_scoring_data(self) -> "CandidateApplicationResponse":
        self.ai_score = None
        self.ai_fit_summary = None
        self.ai_strengths = None
        self.ai_weaknesses = None
        self.ai_score_computed_at = None
        self.ai_score_failure = None
        self.match_score = None
        self.score_computed_at = None
        return self


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
