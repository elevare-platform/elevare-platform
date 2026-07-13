"""Database operations for the jobs module."""

from uuid import UUID

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import JobNotFoundError
from app.core.pagination import paginate_cursor
from app.modules.jobs.enums import JobStatus, ModerationStatus
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import JobCreateRequest, JobFilterParams, JobUpdateRequest
from app.modules.users.models import User


class JobRepository:
    """Data-access layer for :class:`Job` records."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session."""
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
            select(Job).where(Job.id == job_id).options(self._with_employer_profile())
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
        if filters.work_location:
            stmt = stmt.where(Job.work_location == filters.work_location.value)
        if filters.seniority_level:
            stmt = stmt.where(Job.seniority_level == filters.seniority_level.value)
        if filters.min_years_experience is not None:
            stmt = stmt.where(
                (Job.required_years_experience == None)  # noqa: E711
                | (Job.required_years_experience >= filters.min_years_experience)
            )
        if filters.max_years_experience is not None:
            stmt = stmt.where(
                (Job.required_years_experience == None)  # noqa: E711
                | (Job.required_years_experience <= filters.max_years_experience)
            )
        if filters.location:
            stmt = stmt.where(Job.location.ilike(f"%{filters.location}%"))
        # Full-text search across title and structured description fields
        if filters.q:
            term = f"%{filters.q}%"
            from sqlalchemy import or_

            stmt = stmt.where(
                or_(
                    Job.title.ilike(term),
                    Job.about_the_role.ilike(term),
                    Job.key_responsibilities.ilike(term),
                    Job.requirements.ilike(term),
                    Job.technical_competencies.ilike(term),
                )
            )

        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def list_by_employer(
        self,
        employer_id: UUID,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated jobs owned by a specific employer, with application counts.

        Application counts are fetched in a single bulk query and attached to
        each Job instance as a transient ``application_count`` attribute.
        This avoids N+1 queries and doesn't require modifying paginate_cursor.
        """
        from app.modules.applications.models import Application

        stmt = (
            select(Job)
            .where(Job.employer_id == employer_id)
            .options(self._with_employer_profile())
        )
        result = await paginate_cursor(stmt, self._db, cursor, limit)
        jobs = result["items"]

        if jobs:
            job_ids = [j.id for j in jobs]
            # Single query: count applications grouped by job_id
            counts_result = await self._db.execute(
                select(Application.job_id, func.count(Application.id).label("cnt"))
                .where(Application.job_id.in_(job_ids))
                .group_by(Application.job_id)
            )
            counts = {row.job_id: row.cnt for row in counts_result}

            # Single query: count talent pool profiles grouped by job_id
            from app.modules.talent_pool.models import TalentPoolProfiles

            pipeline_result = await self._db.execute(
                select(
                    TalentPoolProfiles.sourced_for_job_id,
                    func.count(TalentPoolProfiles.id).label("cnt"),
                )
                .where(TalentPoolProfiles.sourced_for_job_id.in_(job_ids))
                .group_by(TalentPoolProfiles.sourced_for_job_id)
            )
            pipeline_counts = {
                row.sourced_for_job_id: row.cnt for row in pipeline_result
            }

            for job in jobs:
                job.application_count = counts.get(job.id, 0)
                job.pipeline_count = pipeline_counts.get(job.id, 0)

        return result

    async def list_all(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return all jobs regardless of status — admin only."""
        stmt = select(Job).options(self._with_employer_profile())
        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def get_sitemap_jobs(self) -> list[Row]:
        """Return all ACTIVE jobs with only the fields needed for sitemap.xml."""
        stmt = (
            select(
                Job.id,
                Job.updated_at,
            )
            .where(
                Job.status == JobStatus.ACTIVE.value,
                Job.moderation_status == ModerationStatus.APPROVED.value,
            )
            .order_by(Job.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return result.all()
