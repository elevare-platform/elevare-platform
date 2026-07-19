"""Introduction request endpoints — authenticated employer + public magic-link."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.introductions.schemas import (
    IntroductionRequestResponse,
    IntroductionSummaryResponse,
)
from app.modules.introductions.service import IntroductionService
from app.modules.users.models import User

router = APIRouter()
public_router = APIRouter()
# Separate from `router` (which is nested under /api/v1/jobs by jobs/router.py) —
# this one is mounted directly at /api/v1/introductions since "mine" spans all jobs.
mine_router = APIRouter()


@mine_router.get(
    "/mine",
    response_model=list[IntroductionSummaryResponse],
    status_code=200,
)
async def list_my_introductions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Return every introduction request this employer has made, across all jobs."""
    service = IntroductionService(db)
    return await service.list_mine(employer_id=current_user.id)


@router.post(
    "/{job_id}/talent-matches/{profile_id}/introductions",
    response_model=IntroductionRequestResponse,
    status_code=201,
)
async def request_introduction(
    job_id: UUID,
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Request an introduction to a matched candidate. Costs 1 credit."""
    service = IntroductionService(db)
    return await service.request_introduction(
        employer_id=current_user.id,
        job_id=job_id,
        talent_pool_profile_id=profile_id,
    )


@router.get(
    "/{job_id}/talent-matches/{profile_id}/introductions",
    response_model=list[IntroductionRequestResponse],
    status_code=200,
)
async def list_introductions_for_profile(
    job_id: UUID,
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Return all introduction requests this employer has made for a specific profile+job."""
    service = IntroductionService(db)
    return await service.list_for_profile(
        employer_id=current_user.id,
        job_id=job_id,
        talent_pool_profile_id=profile_id,
    )


@router.get(
    "/{job_id}/introductions",
    response_model=list[IntroductionRequestResponse],
    status_code=200,
)
async def list_introductions_for_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Return all introduction requests this employer has made for a job."""
    service = IntroductionService(db)
    return await service.list_for_job(
        employer_id=current_user.id,
        job_id=job_id,
    )


@public_router.get("/introductions/{token}/accept")
async def accept_introduction(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public magic-link endpoint — candidate accepts an introduction request."""
    service = IntroductionService(db)
    return await service.accept(token)


@public_router.get("/introductions/{token}/decline")
async def decline_introduction(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public magic-link endpoint — candidate declines an introduction request."""
    service = IntroductionService(db)
    return await service.decline(token)
