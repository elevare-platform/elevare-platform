"""Business logic for the users module."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedException
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import (
    EmployerProfileResponse,
    EmployerProfileUpdateRequest,
)

logger = logging.getLogger(__name__)


class UserService:
    """Business logic for user profile management."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._user_repo = UserRepository(db)

    async def update_employer_profile(
        self, user_id: UUID, data: EmployerProfileUpdateRequest
    ) -> EmployerProfileResponse:
        """Create or update the employer's company profile.

        Raises:
            PermissionDeniedException: If the authenticated user is not an EMPLOYER.

        """
        user = await self._user_repo.get_user_by_id(user_id)

        if not user or user.role != "EMPLOYER":
            raise PermissionDeniedException(
                message="Only employer accounts can update a company profile"
            )

        profile = await self._user_repo.upsert_employer_profile(user_id, data)
        await self._db.commit()

        return EmployerProfileResponse.model_validate(profile)
