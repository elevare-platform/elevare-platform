"""HTTP endpoints for the users/employer module."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.users.models import User
from app.modules.users.schemas import (
    EmployerProfileResponse,
    EmployerProfileUpdateRequest,
)
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.patch("/profile", response_model=EmployerProfileResponse, status_code=200)
async def update_employer_profile(
    data: EmployerProfileUpdateRequest,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> EmployerProfileResponse:
    """Create or update the authenticated employer's company profile.

    Flips ``is_profile_complete`` to True once required fields are saved,
    which unlocks job posting for this account.

    Args:
        data: Validated company profile payload.
        current_user: The authenticated EMPLOYER user.
        db: Injected async database session.

    Returns:
        The updated EmployerProfileResponse.

    """
    return await UserService(db).update_employer_profile(current_user.id, data)
