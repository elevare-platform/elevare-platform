"""HTTP endpoints for the applications module."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_candidate, get_db, require_role
from app.modules.applications.schema import (
    ApplicationCreateRequest,
    ApplicationFilters,
    ApplicationList,
    ApplicationResponse,
    CandidateApplicationList,
    CandidateApplicationResponse,
    HasAppliedBatchRequest,
    UpdateApplicationStatus,
)
from app.modules.applications.service import ApplicationService
from app.modules.candidates.models import CandidateProfile
from app.modules.users.models import User

router = APIRouter()


@router.post("", status_code=201, response_model=CandidateApplicationResponse)
async def apply_for_job(
    data: ApplicationCreateRequest,
    background_tasks: BackgroundTasks,
    # get_candidate already calls get_current_user internally — no need for
    # a separate require_role dep here; role is enforced via get_candidate
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Candidate applies to a job."""
    return await ApplicationService(db).apply_to_job(
        candidate_id=candidate.user_id,
        job_id=data.job_id,
        background_tasks=background_tasks,
        cv_id=data.cv_id,
        cover_letter=data.cover_letter,
    )


@router.get("/me", status_code=200, response_model=CandidateApplicationList)
async def my_applications(
    # Filters and pagination come as query params, not a request body
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> ApplicationList:
    """Candidate views their own applications."""
    filters = ApplicationFilters(status=status.upper() if status else None)
    return await ApplicationService(db).get_my_applications(
        candidate_id=candidate.user_id,
        filters=filters,
        cursor=cursor,
        limit=limit,
    )


@router.patch(
    "/{application_id}/withdraw",
    status_code=200,
    response_model=CandidateApplicationResponse,
)
async def withdraw_application(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Candidate withdraws their application. Only allowed from submitted or reviewing."""
    return await ApplicationService(db).withdraw_application(
        application_id=application_id,
        candidate_id=candidate.user_id,
    )


@router.get("/job/{job_id}", status_code=200, response_model=ApplicationList)
async def get_job_applicants(
    job_id: uuid.UUID,
    status: str | None = Query(default=None),
    sort: str | None = Query(
        default=None,
        description="Sort by 'ai_score' (descending) or omit for default (created_at desc)",
    ),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationList:
    """Employer or admin views applicants for a job."""
    filters = ApplicationFilters(
        status=status.upper() if status else None,
        sort=sort,
    )
    return await ApplicationService(db).get_job_applicants(
        job_id=job_id,
        current_user_id=current_user.id,
        current_user_role=current_user.role,
        filters=filters,
        cursor=cursor,
        limit=limit,
    )


@router.patch(
    "/{application_id}/status", status_code=200, response_model=ApplicationResponse
)
async def update_application_status(
    application_id: uuid.UUID,
    data: UpdateApplicationStatus,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    """Employer or admin updates an application status."""
    return await ApplicationService(db).update_application_status(
        application_id=application_id,
        new_status=data.new_status.value,
        updated_by=current_user.id,
        background_tasks=background_tasks,
    )


@router.get("/{job_id}/has-applied", status_code=200)
async def has_applied(
    job_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check whether the current candidate has already applied to a job."""
    result = await ApplicationService(db).has_applied(
        candidate_id=candidate.user_id,
        job_id=job_id,
    )
    return {"has_applied": result}


@router.post("/has-applied/batch", status_code=200)
async def has_applied_batch(
    data: HasAppliedBatchRequest,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a map of job_id → has_applied for a list of job IDs."""
    result = await ApplicationService(db).has_applied_batch(
        candidate_id=candidate.user_id,
        job_ids=data.job_ids,
    )
    return result
