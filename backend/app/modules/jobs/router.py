"""HTTP endpoints for the jobs module."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.jobs.schemas import (
    JobCreateRequest,
    JobFilterParams,
    JobListResponse,
    JobResponse,
    JobUpdateRequest,
)
from app.modules.jobs.service import JobService
from app.modules.users.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=JobListResponse, status_code=200)
async def list_jobs(
    filters: JobFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List active jobs with optional filters and cursor pagination.

    Public — no authentication required.
    """
    return await JobService(db).list_jobs(
        filters=filters,
        cursor=filters.cursor,
        limit=filters.limit,
    )


@router.get("/mine", response_model=JobListResponse, status_code=200)
async def list_my_jobs(
    cursor: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """Return all jobs owned by the authenticated employer.

    Must be declared before /{job_id} to prevent route conflict.
    """
    return await JobService(db).list_employer_jobs(
        employer=current_user,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobResponse, status_code=200)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Return a single job by ID. Public — no authentication required."""
    return await JobService(db).get_job_by_id(job_id)


# ---------------------------------------------------------------------------
# Employer endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreateRequest,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new draft job. Employer only."""
    return await JobService(db).create_job(data, employer=current_user)


@router.patch("/{job_id}", response_model=JobResponse, status_code=200)
async def update_job(
    job_id: UUID,
    data: JobUpdateRequest,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Partially update a job. Only the owning employer can update."""
    return await JobService(db).update_job(job_id, data, current_user)


@router.post("/{job_id}/publish", response_model=JobResponse, status_code=200)
async def publish_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Publish a draft job (DRAFT → ACTIVE). Only the owning employer."""
    return await JobService(db).publish_job(job_id, current_user)


@router.post("/{job_id}/close", response_model=JobResponse, status_code=200)
async def close_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Close a job (ACTIVE → CLOSED). Employer (own jobs) or Admin (any job)."""
    return await JobService(db).close_job(job_id, current_user)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get("/admin/jobs", response_model=JobListResponse, status_code=200)
async def admin_list_jobs(
    cursor: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """Return all jobs regardless of status. Admin only."""
    return await JobService(db).admin_list_jobs(cursor=cursor, limit=limit)
