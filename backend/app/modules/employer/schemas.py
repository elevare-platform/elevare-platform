"""Pydantic schemas for employer-specific responses."""

from pydantic import BaseModel


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
