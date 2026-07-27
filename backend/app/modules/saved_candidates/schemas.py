"""Pydantic schemas for the saved-candidates module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, model_validator


class SaveCandidateRequest(BaseModel):
    """Payload to save (or update the note on) a candidate.

    Accepts either id — ``candidate_profile_id`` is what's on hand in
    contexts like the applicants list (which doesn't carry the underlying
    talent_pool_profiles id directly); the service resolves it to the real
    talent_pool_profile_id before saving, since that's the single id every
    candidate (self-registered or sourced) is uniformly addressable by.
    """

    talent_pool_profile_id: UUID | None = None
    candidate_profile_id: UUID | None = None
    note: str | None = None

    @model_validator(mode="after")
    def require_one_id(self) -> SaveCandidateRequest:
        if not self.talent_pool_profile_id and not self.candidate_profile_id:
            raise ValueError(
                "Either talent_pool_profile_id or candidate_profile_id is required"
            )
        return self


class SavedCandidateResponse(BaseModel):
    """A single saved candidate, enriched with display fields for the list UI."""

    id: UUID  # saved_candidates row id
    talent_pool_profile_id: UUID
    candidate_profile_id: UUID | None = None
    ownership: str  # "self_registered" | "own_sourced" | "admin_sourced"
    candidate_name: str | None = None
    current_title: str | None = None
    location: str | None = None
    years_of_experience: int | None = None
    skills: list[str] = []
    note: str | None = None
    saved_at: datetime

    model_config = {"from_attributes": True}


class SavedCandidateListResponse(BaseModel):
    items: list[SavedCandidateResponse]
    total: int


class SavedCandidateIdsResponse(BaseModel):
    """The set of saved ids — cheap check for heart state on cards.

    Two id spaces because callers address candidates differently depending
    on where they're rendered: search/AI-matches results carry
    talent_pool_profile_id directly, while the applicants list only has
    candidate_profile_id on hand.
    """

    talent_pool_profile_ids: list[UUID]
    candidate_profile_ids: list[UUID]
