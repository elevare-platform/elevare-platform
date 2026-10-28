"""Pydantic schemas for the interview-list module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


class InterviewListAddRequest(BaseModel):
    """Payload to add (or update the note on) a candidate for a specific job.

    Accepts either id — mirrors ``SaveCandidateRequest`` in the
    saved_candidates module for the same reason: the applicants list only
    has ``candidate_profile_id`` on hand, not the underlying
    talent_pool_profile_id.
    """

    job_id: UUID
    talent_pool_profile_id: UUID | None = None
    candidate_profile_id: UUID | None = None
    note: str | None = None

    @model_validator(mode="after")
    def require_one_id(self) -> InterviewListAddRequest:
        if not self.talent_pool_profile_id and not self.candidate_profile_id:
            raise ValueError(
                "Either talent_pool_profile_id or candidate_profile_id is required"
            )
        return self


class InterviewListAddResponse(BaseModel):
    """Response for adding a candidate to a job's interview list."""

    message: str
    talent_pool_profile_id: UUID


class InterviewListEntryResponse(BaseModel):
    """A single interview-list entry, enriched for display."""

    id: UUID  # interview_list_entries row id
    job_id: UUID
    talent_pool_profile_id: UUID
    candidate_profile_id: UUID | None = None
    ownership: str  # "self_registered" | "own_sourced" | "admin_sourced"
    has_cv_access: bool = True
    # An email typed in to send the interview to: no CV and no profile exist, so the row shows
    # the email as its name and offers nothing to open.
    email_only: bool = False
    candidate_name: str | None = None
    # True when ``candidate_name`` is the one an employer typed in, not the one read from the CV.
    name_overridden: bool = False
    current_title: str | None = None
    location: str | None = None
    years_of_experience: int | None = None
    skills: list[str] = []
    note: str | None = None
    added_at: datetime
    interview_status: str | None = None
    """Current ``InterviewStatus`` for this candidate on this job, or ``None`` if never invited."""
    interview_failure: str | None = None
    """Why a FAILED interview failed: ``NEVER_FINISHED`` (the recording never arrived, nothing was
    scored; the employer can reopen it or start it over) or ``SCORING_FAILED`` (the recording
    arrived and scoring failed). ``None`` when the interview has not failed."""

    model_config = {"from_attributes": True}


class InterviewListResponse(BaseModel):
    items: list[InterviewListEntryResponse]
    total: int


class InterviewListIdsResponse(BaseModel):
    """The set of ids on the interview list for one job — cheap check for button state."""

    talent_pool_profile_ids: list[UUID]
    candidate_profile_ids: list[UUID]
