"""Business logic for the jobs module."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    PermissionDeniedException,
    ProfileIncompleteException,
    ValidationException,
)
from app.modules.jobs.enums import JobStatus, ModerationStatus
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import (
    JobCreateRequest,
    JobFilterParams,
    JobListResponse,
    JobResponse,
    JobUpdateRequest,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)

# Valid status transitions — enforced in the service layer
_VALID_TRANSITIONS: dict[JobStatus, list[JobStatus]] = {
    JobStatus.DRAFT: [JobStatus.ACTIVE],
    JobStatus.ACTIVE: [JobStatus.CLOSED],
    JobStatus.CLOSED: [],  # closed jobs cannot be re-opened without admin action
}


class JobService:
    """Business logic for job listing lifecycle management."""

    def __init__(self, db: AsyncSession):
        """Initialise the service with an async database session."""
        self._db = db
        self._repo = JobRepository(db)
        self._user_repo = UserRepository(db)

    async def create_job(self, data: JobCreateRequest, employer: User) -> JobResponse:
        """Create a draft job owned by the authenticated employer."""
        employer = await self._user_repo.get_user_by_id(employer.id)

        if not employer.employer_profile or not employer.employer_profile.is_profile_complete:
            raise ProfileIncompleteException()
        job = await self._repo.create(data, employer_id=employer.id)
        await self._db.commit()
        return JobResponse.from_job(job)

    async def publish_job(self, job_id: UUID, current_user: User) -> JobResponse:
        """Transition a job from DRAFT to ACTIVE.

        Raises
        ------
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job.
            ValidationException: If the transition is not valid.

        """
        job = await self._repo.get_by_id(job_id)
        self._check_ownership(job, current_user)
        self._check_transition(job, JobStatus.ACTIVE)
        if job.moderation_status == ModerationStatus.APPROVED.value:
            job = await self._repo.set_status(job, JobStatus.ACTIVE)
            await self._db.commit()
            return JobResponse.from_job(job)
        raise ValidationException("Job listing isn't approved yet")

    async def close_job(self, job_id: UUID, current_user: User) -> JobResponse:
        """Transition a job from ACTIVE to CLOSED.

        Admins can close any job. Employers can only close their own.

        Raises
        ------
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job and is not admin.
            ValidationException: If the transition is not valid.

        """
        job = await self._repo.get_by_id(job_id)

        # Admins can close any job; employers only their own
        if current_user.role != "ADMIN":
            self._check_ownership(job, current_user)

        self._check_transition(job, JobStatus.CLOSED)
        job = await self._repo.set_status(job, JobStatus.CLOSED)
        await self._db.commit()
        return JobResponse.from_job(job)

    async def update_job(
        self, job_id: UUID, data: JobUpdateRequest, current_user: User
    ) -> JobResponse:
        """Update a job partially. Only the owning employer can modify it.

        If description, required_skills, or seniority_level change, re-fires
        score_application_task for every active application on this job so
        ai_score stays consistent with the updated job inputs.

        Raises
        ------
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job.

        """
        job = await self._repo.get_by_id(job_id)
        self._check_ownership(job, current_user)

        # Detect whether any scoring-relevant fields are changing
        scoring_fields = {"description", "required_skills", "seniority_level"}
        update_data = data.model_dump(exclude_unset=True)
        scoring_changed = bool(scoring_fields & update_data.keys())

        job = await self._repo.update(job, data)
        await self._db.commit()

        # Re-fire scoring for all applications on this job if inputs changed
        if scoring_changed:
            from app.modules.ai.tasks import score_application_task
            from app.modules.applications.repository import ApplicationRepository

            app_repo = ApplicationRepository(self._db)
            application_ids = await app_repo.get_application_ids_for_job(job_id)
            for app_id in application_ids:
                score_application_task.delay(str(app_id))
            if application_ids:
                logger.info(
                    "update_job: re-queued scoring for %d applications on job %s",
                    len(application_ids),
                    job_id,
                )

        return JobResponse.from_job(job)

    async def get_job_by_id(self, job_id: UUID) -> JobResponse:
        """Return a single job by ID. Public — no ownership check."""
        job = await self._repo.get_by_id(job_id)
        return JobResponse.from_job(job)

    async def list_jobs(
        self,
        filters: JobFilterParams,
        cursor: str | None = None,
        limit: int = 20,
    ) -> JobListResponse:
        """Return paginated active jobs with optional filters. Public endpoint."""
        result = await self._repo.list_active(filters, cursor, limit)
        return JobListResponse(
            items=[JobResponse.from_job(j) for j in result["items"]],
            next_cursor=result["next_cursor"],
            count=result["count"],
            total=result["total"],
        )

    async def list_employer_jobs(
        self,
        employer: User,
        cursor: str | None = None,
        limit: int = 20,
    ) -> JobListResponse:
        """Return paginated jobs owned by the authenticated employer."""
        result = await self._repo.list_by_employer(employer.id, cursor, limit)
        return JobListResponse(
            items=[JobResponse.from_job(j) for j in result["items"]],
            next_cursor=result["next_cursor"],
            count=result["count"],
            total=result["total"],
        )

    async def admin_list_jobs(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> JobListResponse:
        """Return all jobs regardless of status. Admin only."""
        result = await self._repo.list_all(cursor, limit)
        return JobListResponse(
            items=[JobResponse.from_job(j) for j in result["items"]],
            next_cursor=result["next_cursor"],
            count=result["count"],
            total=result["total"],
        )

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    @staticmethod
    def _check_ownership(job, current_user: User) -> None:
        """Raise PermissionDeniedException if the user does not own the job."""
        if job.employer_id != current_user.id:
            raise PermissionDeniedException(
                message="You do not have permission to modify this job"
            )

    @staticmethod
    def _check_transition(job, target: JobStatus) -> None:
        """Raise ValidationException if the status transition is not allowed."""
        current = JobStatus(job.status)
        if target not in _VALID_TRANSITIONS.get(current, []):
            raise ValidationException(
                message=f"Cannot transition job from {current.value} to {target.value}"
            )
