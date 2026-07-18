"""Data-access layer for job applications."""

import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import paginate_cursor
from app.modules.applications.enums import ApplicationStatus
from app.modules.applications.models import Application
from app.modules.applications.schema import ApplicationFilters
from app.modules.jobs.models import Job
from app.modules.users.models import User


class ApplicationRepository:
    """Data-access layer for :class:`Application` records."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session."""
        self._db = db

    def _base_options(self):
        """Eager-load relationships needed to build ApplicationResponse."""
        return [
            # job → employer (User) → employer_profile (company name, logo)
            selectinload(Application.job)
            .selectinload(Job.employer)
            .selectinload(User.employer_profile),
            # candidate (User) → candidate_profile (location, experience)
            selectinload(Application.candidate).selectinload(User.candidate_profile),
        ]

    async def get_by_id(self, application_id: uuid.UUID) -> Application | None:
        """Fetch an application by its primary key with all relationships eager-loaded."""
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(*self._base_options())
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        cv_id: uuid.UUID | None,
        cover_letter: str | None,
    ) -> Application:
        """Persist a new application record and return it."""
        application = Application(
            candidate_id=candidate_id,
            job_id=job_id,
            cv_id=cv_id,
            cover_letter=cover_letter,
            status=ApplicationStatus.SUBMITTED.value,
        )
        self._db.add(application)
        await self._db.flush()
        await self._db.refresh(application)
        return application

    async def has_applied(
        self, candidate_id: uuid.UUID, job_id: uuid.UUID
    ) -> Application | None:
        """Return the existing application row or None — used as a bool check."""
        stmt = select(Application).where(
            and_(
                Application.candidate_id == candidate_id,
                Application.job_id == job_id,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def has_applied_batch(
        self, candidate_id: uuid.UUID, job_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Return the set of job_ids from the given list that the candidate has applied to."""
        if not job_ids:
            return set()
        stmt = select(Application.job_id).where(
            and_(
                Application.candidate_id == candidate_id,
                Application.job_id.in_(job_ids),
            )
        )
        result = await self._db.execute(stmt)
        return {row[0] for row in result.fetchall()}

    async def update(self, application_id: uuid.UUID, data: dict) -> Application:
        """Apply a partial update dict to an application and return the updated record."""
        application = await self.get_by_id(application_id)
        for key, value in data.items():
            setattr(application, key, value)
        await self._db.flush()
        await self._db.refresh(application)
        return application

    async def get_all_applications_by_candidate(
        self,
        candidate_id: uuid.UUID,
        filters: ApplicationFilters,
        cursor: str | None = None,
        limit: int = 20,
    ):
        """Return a paginated cursor result of all applications for a candidate."""
        stmt = (
            select(Application)
            .where(Application.candidate_id == candidate_id)
            .options(*self._base_options())
            .order_by(Application.created_at.desc())
        )

        if filters and filters.status:
            stmt = stmt.where(Application.status == filters.status.value)

        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def get_application_ids_for_job(self, job_id: uuid.UUID) -> list[uuid.UUID]:
        """Return all application IDs for a given job. Used to re-fire scoring tasks."""
        stmt = select(Application.id).where(Application.job_id == job_id)
        result = await self._db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def get_user_ids_for_job(self, job_id: uuid.UUID) -> list[uuid.UUID]:
        """Return all candidate IDs for a given job."""
        stmt = select(Application.candidate_id).where(Application.job_id == job_id)
        result = await self._db.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def get_job_applicants(
        self,
        job_id: uuid.UUID,
        filters: ApplicationFilters,
        cursor: str | None = None,
        limit: int = 20,
    ):
        """Return a paginated cursor result of applicants for a specific job."""
        # Default order: created_at desc. If sort=ai_score, order by ai_score desc nulls last.
        order_by = (
            Application.ai_score.desc().nulls_last()
            if filters and filters.sort == "ai_score"
            else Application.created_at.desc()
        )

        stmt = (
            select(Application)
            .where(Application.job_id == job_id)
            .options(
                selectinload(Application.job)
                .selectinload(Job.employer)
                .selectinload(User.employer_profile),
                selectinload(Application.candidate).selectinload(
                    User.candidate_profile
                ),
            )
            .order_by(order_by)
        )

        if filters and filters.status:
            stmt = stmt.where(Application.status == filters.status.value)

        return await paginate_cursor(stmt, self._db, cursor, limit)
