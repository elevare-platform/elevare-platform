"""Business logic for employer-specific operations."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employer.repository import EmployerRepository
from app.modules.employer.schemas import EmployerStats


class EmployerService:
    """Business logic for employer-specific operations."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._repo = EmployerRepository(db)

    async def get_employer_stats(self, employer_id: UUID) -> EmployerStats:
        """Return job statistics scoped to the given employer.

        Args:
            employer_id: The UUID of the employer user.

        Returns:
            EmployerStats with counts for total, active, draft, and closed jobs.

        """
        return await self._repo.get_stats(employer_id)
