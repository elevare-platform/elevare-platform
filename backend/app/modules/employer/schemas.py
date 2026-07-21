"""Pydantic schemas for employer-specific responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmployerStats(BaseModel):
    """Aggregated job statistics for an employer dashboard.

    Attributes:
        total_jobs: Total number of jobs posted by this employer.
        active_jobs: Jobs currently in ACTIVE status.
        draft_jobs: Jobs in DRAFT status (not yet published).
        closed_jobs: Jobs in CLOSED status.
        total_applications: Total applications received (Phase 4).

    """

    total_jobs: int
    active_jobs: int
    draft_jobs: int
    closed_jobs: int
    total_applications: int = 0


class KYCDocumentResponse(BaseModel):
    """A single KYC document uploaded by an employer."""

    id: uuid.UUID
    document_type: str
    filename: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KYCStatusResponse(BaseModel):
    """KYC status for the authenticated employer."""

    kyc_status: str | None
    kyc_rejection_reason: str | None
    kyc_submitted_at: datetime | None
    kyc_reviewed_at: datetime | None
    documents: list[KYCDocumentResponse]

    model_config = ConfigDict(from_attributes=True)
