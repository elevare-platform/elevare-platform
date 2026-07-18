"""Pydantic schemas for the introductions module."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IntroductionRequestResponse(BaseModel):
    """Serialized introduction request returned to the employer."""

    id: UUID
    employer_id: UUID
    job_id: UUID
    talent_pool_profile_id: UUID
    status: str
    expires_at: datetime
    responded_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntroductionSummaryResponse(BaseModel):
    """Enriched introduction request for the employer's cross-job 'mine' list."""

    id: UUID
    job_id: UUID
    job_title: str
    talent_pool_profile_id: UUID
    candidate_name: str | None = None
    candidate_current_title: str | None = None
    status: str
    expires_at: datetime
    responded_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntroductionResponsePage(BaseModel):
    """Payload for the public accept/decline confirmation page."""

    status: str  # ACCEPTED | DECLINED | EXPIRED | already_responded
    message: str
