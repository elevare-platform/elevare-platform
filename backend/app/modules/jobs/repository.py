"""Database operations for the jobs module."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import JobNotFoundError
from app.core.pagination import paginate_cursor
from app.modules.jobs.enums import JobStatus
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import JobCreateRequest, JobFilterParams, JobUpdateRequest
from app.modules.users.models import User


class JobRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    @staticmethod
    def _with_employer_profile():
        """Return selectinload options to load employer + their profile in one query."""
        return selectinload(Job.employer).selectinload(User.employer_profile)

    async def create(self, data: JobCreateRequest, employer_id: UUID) -> Job:
        """Insert a new draft job owned by the given employer."""
        job = Job(
            **data.model_dump(),
            employer_id=employer_id,
            status=JobStatus.DRAFT.value,
        )
        self._db.add(job)
        await self._db.flush()
        # Re-fetch with employer profile loaded so from_job() can access it
        return await self.get_by_id(job.id)

    async def get_by_id(self, job_id: UUID) -> Job:
        """Return a job by ID or raise JobNotFoundError."""
        stmt = (
            select(Job)
            .where(Job.id == job_id)
            .options(self._with_employer_profile())
        )
        result = await self._db.execute(stmt)
        job = result.scalar_one_or_none()
        if job is None:
            raise JobNotFoundError()
        return job

    async def update(self, job: Job, data: JobUpdateRequest) -> Job:
        """Apply partial update to an already-fetched job instance."""
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(job, key, value)
        await self._db.flush()
        return await self.get_by_id(job.id)

    async def set_status(self, job: Job, status: JobStatus) -> Job:
        """Set the job status directly — caller enforces valid transitions."""
        job.status = status.value
        await self._db.flush()
        return await self.get_by_id(job.id)

    async def list_active(
        self,
        filters: JobFilterParams,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated active jobs with optional filters."""
        stmt = (
            select(Job)
            .where(Job.status == JobStatus.ACTIVE.value)
            .options(self._with_employer_profile())
        )

        if filters.contract_type:
            stmt = stmt.where(Job.contract_type == filters.contract_type.value)
        if filters.work_model:
            stmt = stmt.where(Job.work_model == filters.work_model.value)
        if filters.location:
            stmt = stmt.where(Job.location.ilike(f"%{filters.location}%"))

        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def list_by_employer(
        self,
        employer_id: UUID,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated jobs owned by a specific employer."""
        stmt = (
            select(Job)
            .where(Job.employer_id == employer_id)
            .options(self._with_employer_profile())
        )
        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def list_all(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return all jobs regardless of status — admin only."""
        stmt = select(Job).options(self._with_employer_profile())
        return await paginate_cursor(stmt, self._db, cursor, limit)
