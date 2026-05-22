"""HTTP endpoints for employer-specific operations."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.employer.schemas import EmployerStats
from app.modules.employer.service import EmployerService
from app.modules.users.models import User
from app.modules.users.schemas import (
    EmployerProfileResponse,
    EmployerProfileUpdateRequest,
)
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/stats", response_model=EmployerStats, status_code=200)
async def get_employer_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
) -> EmployerStats:
    """Return job statistics for the authenticated employer.

    Args:
        db: Injected async database session.
        current_user: The authenticated EMPLOYER or ADMIN user.

    Returns:
        EmployerStats with job counts scoped to this employer.

    """
    return await EmployerService(db).get_employer_stats(current_user.id)


@router.patch("/profile", response_model=EmployerProfileResponse, status_code=200)
async def update_employer_profile(
    data: EmployerProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
) -> EmployerProfileResponse:
    """Create or update the authenticated employer's company profile.

    Flips ``is_profile_complete`` to True once required fields are saved,
    which unlocks job posting for this account.

    Args:
        data: Validated company profile payload.
        db: Injected async database session.
        current_user: The authenticated EMPLOYER user.

    Returns:
        The updated EmployerProfileResponse.

    """
    return await UserService(db).update_employer_profile(current_user.id, data)


@router.get("/profile", response_model=EmployerProfileResponse, status_code=200)
async def get_employer_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
) -> EmployerProfileResponse:
    """Return the authenticated employer's company profile.

    Args:
        db: Injected async database session.
        current_user: The authenticated EMPLOYER or ADMIN user.

    Returns:
        The EmployerProfileResponse for this employer.

    """
    return await UserService(db).get_employer_profile(current_user.id)
