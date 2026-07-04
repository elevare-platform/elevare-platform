"""Data-access layer for employer-specific queries."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import Job

from .schemas import EmployerStats


class EmployerRepository:
    """Handles database queries scoped to a specific employer."""

    def __init__(self, db: AsyncSession):
        """Initialise with an async database session."""
        self._db = db

    async def get_stats(self, employer_id) -> EmployerStats:
        """Return aggregated job counts for the given employer.

        Args:
            employer_id: The UUID of the employer user.

        Returns:
            EmployerStats with total, active, draft, and closed job counts.
            Returns zero counts if the employer has no jobs yet.

        """
        stmt = select(
            func.count(Job.id).label("total"),
            func.count(Job.id).filter(Job.status == "ACTIVE").label("active"),
            func.count(Job.id).filter(Job.status == "DRAFT").label("draft"),
            func.count(Job.id).filter(Job.status == "CLOSED").label("closed")
        ).where(
            Job.employer_id == employer_id
        )

        result = await self._db.execute(stmt)

        row = result.mappings().one_or_none()

        # Handle case where employer has no jobs yet
        if not row:
            return EmployerStats(
                total_jobs=0,
                active_jobs=0,
                draft_jobs=0,
                closed_jobs=0,
            )

        return EmployerStats(
            total_jobs=row["total"],
            active_jobs=row["active"],
            draft_jobs=row["draft"],
            closed_jobs=row["closed"],
            total_applications=0
        )
