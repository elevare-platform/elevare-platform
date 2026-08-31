"""Pydantic schemas for the talent pool module."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

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


class TalentPoolEmailUpdateRequest(BaseModel):
    """Payload for an employer-entered override email on a sourced candidate."""

    email: EmailStr


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
    # General, job-independent CV summary and skills — always valid to show,
    # unlike ai_fit_summary/strengths/weaknesses below which are only
    # meaningful next to a specific job (see ai_score_job_hash staleness
    # handling in get_profile).
    summary: str | None = None
    skills: list[str] = []

    ai_score: int | None = None
    ai_fit_summary: str | None = None
    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    ai_score_computed_at: datetime | None = None

    # Populated by the service only once the requester's access is verified —
    # never present on an unentitled fetch.
    cv_download_url: str | None = None

    # Populated by list_profiles only (get_profile has already resolved
    # access by the time it returns) — lets the frontend decide whether to
    # show "View CV" or "Request Introduction" without a per-row API call.
    ownership: str | None = None  # "self_registered" | "own_sourced" | "admin_sourced"
    has_cv_access: bool | None = None

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
    candidate_profile_id: uuid.UUID | None = None  # None for sourced-only CVs
    ownership: Literal["self_registered", "own_sourced", "admin_sourced"]
    cv_download_url: str | None = None

    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    ai_fit_summary: str | None = None
    is_new: bool = False
    matched_skills: list[str] = []

    @classmethod
    def from_match(
        cls,
        profile: "TalentPoolProfiles",
        similarity_score: int,
        candidate_name: str | None = None,
        current_title: str | None = None,
        profession: str | None = None,
        years_of_experience: int | None = None,
        location: str | None = None,
        top_skills: list[str] | None = None,
        matched_skills: list[str] | None = None,
        ownership: str = "admin_sourced",
        cv_download_url: str | None = None,
        is_new: bool = False,
        assessment_is_current_for_job: bool = True,
    ) -> "TalentMatchResponse":
        return cls(
            profile_id=profile.id,
            similarity_score=max(0, min(100, similarity_score)),
            candidate_name=candidate_name,
            current_title=current_title,
            profession=profession,
            years_of_experience=years_of_experience,
            location=location,
            top_skills=top_skills or [],
            matched_skills=matched_skills or [],
            candidate_profile_id=profile.candidate_profile_id,
            ownership=ownership,
            cv_download_url=cv_download_url,
            ai_strengths=profile.ai_strengths
            if assessment_is_current_for_job
            else None,
            ai_weaknesses=profile.ai_weaknesses
            if assessment_is_current_for_job
            else None,
            ai_fit_summary=profile.ai_fit_summary
            if assessment_is_current_for_job
            else None,
            is_new=is_new,
        )


class TalentMatchListResponse(BaseModel):
    items: list[TalentMatchResponse]
    count: int
    job_id: uuid.UUID
