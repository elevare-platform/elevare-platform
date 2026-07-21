"""Introduction request endpoints — authenticated employer + public magic-link."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.introductions.schemas import (
    AdminIntroductionResponse,
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
# Admin ops queue — mounted directly at /api/v1/admin in main.py. Uses `id`
# (not the public magic-link `token`) since these are authenticated admin
# actions, not unauthenticated link clicks.
admin_router = APIRouter()


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


@router.post(
    "/{job_id}/talent-matches/{profile_id}/notify",
    status_code=200,
)
async def notify_own_sourced(
    job_id: UUID,
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Free notification for a candidate this employer sourced themselves.

    No credit, no accept/decline lifecycle — the employer already has full
    access to this profile, this just flags the role to the candidate.
    """
    service = IntroductionService(db)
    return await service.notify_own_sourced(
        employer_id=current_user.id,
        job_id=job_id,
        talent_pool_profile_id=profile_id,
    )


@router.get(
    "/{job_id}/talent-matches/{profile_id}/notify",
    status_code=200,
)
async def get_notify_status(
    job_id: UUID,
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Return whether this own-sourced candidate has already been notified.

    Lets the frontend restore the button state on page reload instead of
    always showing 'Notify for this role'.
    """
    service = IntroductionService(db)
    return await service.get_notification_status(
        employer_id=current_user.id,
        job_id=job_id,
        talent_pool_profile_id=profile_id,
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


# ===================== ADMIN OPS QUEUE =====================
# Mounted at /api/v1/admin (see main.py) — NOT nested under /api/v1/jobs like
# `router` above. These act on the request's `id` under admin auth, distinct
# from the public `token`-based accept/decline used by the candidate's email
# link (public_router, above).


@admin_router.get(
    "/introductions",
    response_model=list[AdminIntroductionResponse],
    status_code=200,
)
async def list_assigned_introductions(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Return introduction requests routed to this admin's ops queue."""
    service = IntroductionService(db)
    return await service.list_assigned(admin_id=current_user.id, status=status)


@admin_router.post("/introductions/{intro_id}/accept")
async def accept_introduction_admin(
    intro_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Admin marks an introduction request accepted after manual candidate outreach."""
    service = IntroductionService(db)
    return await service.accept_by_id(intro_id)


@admin_router.post("/introductions/{intro_id}/decline")
async def decline_introduction_admin(
    intro_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Admin marks an introduction request declined after manual candidate outreach."""
    service = IntroductionService(db)
    return await service.decline_by_id(intro_id)
