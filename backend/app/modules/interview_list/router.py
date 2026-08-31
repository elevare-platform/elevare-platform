"""HTTP endpoints for the interview list."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.modules.interview_list.schemas import (
    InterviewListAddRequest,
    InterviewListAddResponse,
    InterviewListIdsResponse,
    InterviewListResponse,
)
from app.modules.interview_list.service import InterviewListService
from app.modules.users.models import User

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> InterviewListService:
    return InterviewListService(db)


@router.get("", response_model=InterviewListResponse, status_code=200)
async def list_interview_list(
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: InterviewListService = Depends(get_service),
):
    """Return the interview list for one job."""
    return await service.list_for_job(current_user.id, job_id)


@router.get("/ids", response_model=InterviewListIdsResponse, status_code=200)
async def list_interview_list_ids(
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: InterviewListService = Depends(get_service),
):
    """Return just the ids on this job's interview list — cheap button-state check."""
    return await service.list_ids(current_user.id, job_id)


@router.post("", response_model=InterviewListAddResponse, status_code=201)
async def add_to_interview_list(
    body: InterviewListAddRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: InterviewListService = Depends(get_service),
):
    """Add a candidate to a job's interview list (idempotent)."""
    talent_pool_profile_id = await service.add(
        current_user.id,
        body.job_id,
        body.talent_pool_profile_id,
        body.candidate_profile_id,
        body.note,
    )
    return InterviewListAddResponse(
        message="Added to interview list",
        talent_pool_profile_id=talent_pool_profile_id,
    )


@router.delete("", response_model=SuccessResponse, status_code=200)
async def remove_from_interview_list(
    job_id: uuid.UUID = Query(...),
    talent_pool_profile_id: uuid.UUID | None = Query(default=None),
    candidate_profile_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: InterviewListService = Depends(get_service),
):
    """Remove a candidate from a job's interview list."""
    await service.remove(
        current_user.id, job_id, talent_pool_profile_id, candidate_profile_id
    )
    return SuccessResponse(message="Removed from interview list")
