"""Business logic for the jobs module."""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    JobNotFoundError,
    KYCRequiredException,
    PermissionDeniedException,
    ProfileIncompleteException,
    ValidationException,
)
from app.modules.employer.enums import KYCStatus
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
        """Create a job owned by the authenticated employer or admin.

        Admins bypass the profile-completeness/KYC gate — those checks exist
        to verify a real employer's legitimacy before they can post, which
        doesn't apply to internal admin accounts posting jobs for everyone.
        The KYC half of this can also be switched off entirely for everyone
        via `settings.kyc_enforcement_enabled` (HR-requested toggle) — the
        profile-completeness check is unaffected by that flag.

        Admin-posted jobs also skip the moderation queue entirely and go
        straight to ACTIVE — today every admin is inherently a reviewer, so
        there's no one else to review it. This is a placeholder until admin
        roles are tiered (a future "superadmin" reviewing lower-privilege
        admins' posts); at that point this bypass should be scoped down.
        """
        employer = await self._user_repo.get_user_by_id(employer.id)
        is_admin = employer.role == "ADMIN"

        if not is_admin:
            if not employer.organization or not employer.organization.is_profile_complete:
                raise ProfileIncompleteException()
            if (
                settings.kyc_enforcement_enabled
                and employer.organization.kyc_status != KYCStatus.APPROVED.value
            ):
                raise KYCRequiredException()

        job = await self._repo.create(data, employer_id=employer.id)

        if is_admin:
            job.status = JobStatus.ACTIVE.value
            job.moderation_status = ModerationStatus.APPROVED.value

        await self._db.commit()

        from app.modules.ai.tasks import generate_job_embedding_task

        generate_job_embedding_task.delay(str(job.id))

        if is_admin:
            from app.modules.ai.tasks import score_job_against_talent_pool_task

            score_job_against_talent_pool_task.delay(str(job.id))

        return JobResponse.from_job(job, include_interview_brief=True, include_contact_info=True)

    async def get_or_create_general_interest_job(
        self, employer_id: UUID
    ) -> JobResponse:
        """Return (creating if needed) this employer's "General Interest" placeholder job.

        Deliberately bypasses the profile-completeness/KYC gate in
        ``create_job`` — a brand-new employer with no completed onboarding
        yet should still be able to reach out to a candidate found via
        Candidate Search, same as ``request_introduction`` itself doesn't
        require KYC. This job is never published and stays invisible to
        candidates and the public job board.
        """
        job = await self._repo.get_general_interest_job(employer_id)
        if job is None:
            job = await self._repo.create_general_interest_job(employer_id)
            await self._db.commit()
        return JobResponse.from_job(job, include_interview_brief=True, include_contact_info=True)

    async def publish_job(self, job_id: UUID, current_user: User) -> JobResponse:
        """Transition a job from DRAFT to ACTIVE.

        Raises
        ------
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job.
            ValidationException: If the transition is not valid.

        """
        job = await self._repo.get_by_id(job_id)

        # Admins can publish any job; employers only their own
        if current_user.role != "ADMIN":
            self._check_ownership(job, current_user)

        self._check_transition(job, JobStatus.ACTIVE)
        if job.moderation_status == ModerationStatus.APPROVED.value:
            # Quota check comes last, right before the state change it
            # gates — a job that isn't approved yet, or is already ACTIVE
            # (invalid transition), should fail on that first, not on
            # quota. Quota is a plan/billing concern, not a jobs concern —
            # ask billing rather than re-implementing "how many active
            # jobs does this org have" here. Admins bypass it, same as the
            # KYC/profile checks in create_job — an admin publishing isn't
            # spending any organization's billing allowance.
            if current_user.role != "ADMIN":
                from app.modules.billing.service import BillingService

                billing_service = BillingService(self._db)
                await billing_service.assert_can_post_job(current_user.organization_id)

            job = await self._repo.set_status(job, JobStatus.ACTIVE)
            await self._db.commit()

            from app.modules.ai.tasks import score_job_against_talent_pool_task

            score_job_against_talent_pool_task.delay(str(job_id))

            return JobResponse.from_job(job, include_interview_brief=True, include_contact_info=True)
        raise ValidationException("Job listing isn't approved yet")

    async def resubmit_job(self, job_id: UUID, current_user: User) -> JobResponse:
        """Explicitly resubmit a REJECTED job for another admin review.

        The only way out of REJECTED — a plain edit no longer does this
        implicitly, so the employer must deliberately choose to put the
        listing back in the queue.

        Raises
        ------
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job and is not admin.
            ValidationException: If the job isn't currently REJECTED.

        """
        job = await self._repo.get_by_id(job_id)

        if current_user.role != "ADMIN":
            self._check_ownership(job, current_user)

        if job.moderation_status != ModerationStatus.REJECTED.value:
            raise ValidationException(
                "Only a rejected job can be resubmitted for review"
            )

        job.moderation_status = ModerationStatus.PENDING.value
        job.moderation_reason = None
        await self._db.commit()
        return JobResponse.from_job(job, include_interview_brief=True, include_contact_info=True)

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
        return JobResponse.from_job(job, include_interview_brief=True, include_contact_info=True)

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

        # Admins can update any job; employers only their own
        if current_user.role != "ADMIN":
            self._check_ownership(job, current_user)

        update_data = data.model_dump(exclude_unset=True)

        # REJECTED is a terminal state the employer must explicitly resubmit
        # from (see resubmit_job) — editing no longer silently clears it, so
        # the rejection and its reason stay visible until the employer
        # deliberately asks for another review.
        if (
            current_user.role != "ADMIN"
            and update_data
            and job.status == JobStatus.ACTIVE.value
            and job.moderation_status == ModerationStatus.APPROVED.value
        ):
            # The admin approved the OLD content, not this edit — pull the
            # job offline and re-queue it for review. The employer must
            # publish again once an admin re-approves. Admin edits skip this
            # since the admin is the one who'd be reviewing it anyway.
            job.status = JobStatus.DRAFT.value
            job.moderation_status = ModerationStatus.PENDING.value

        # Detect whether any scoring-relevant fields are changing
        scoring_fields = {
            "about_the_role",
            "key_responsibilities",
            "requirements",
            "preferred_certifications",
            "technical_competencies",
            "what_we_offer",
            "required_skills",
            "seniority_level",
        }
        scoring_changed = bool(scoring_fields & update_data.keys())

        job = await self._repo.update(job, data)
        await self._db.commit()

        # Re-generate embedding if embedding-relevant fields changed
        embedding_fields = {
            "about_the_role",
            "key_responsibilities",
            "requirements",
            "preferred_certifications",
            "technical_competencies",
            "what_we_offer",
            "required_skills",
        }
        if bool(embedding_fields & update_data.keys()):
            from app.modules.ai.tasks import generate_job_embedding_task

            generate_job_embedding_task.delay(str(job.id))

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

        return JobResponse.from_job(job, include_interview_brief=True, include_contact_info=True)

    async def get_job_by_id(
        self, job_id: UUID, requesting_user: User | None
    ) -> JobResponse:
        """Return a single job by ID.

        Public for ACTIVE/CLOSED jobs. A DRAFT job (unpublished — including
        one pulled offline for re-review) is only visible to its owning
        employer or an admin; anyone else gets a 404, same as a nonexistent
        job, so a leaked draft URL doesn't even confirm the job exists.
        """
        job = await self._repo.get_by_id(job_id)
        is_owner = (
            requesting_user is not None and requesting_user.id == job.employer_id
        )
        is_admin = requesting_user is not None and requesting_user.role == "ADMIN"
        if job.status == JobStatus.DRAFT.value and not is_owner and not is_admin:
            raise JobNotFoundError()
        return JobResponse.from_job(job, include_interview_brief=is_owner or is_admin, include_contact_info=is_owner or is_admin)

    async def delete_job(self, job_id: UUID, current_user: User) -> None:
        """Delete a DRAFT job. Owning employer or admin only.

        Restricted to DRAFT — a job that has ever been published may have
        applications, talent matches, or public visibility tied to it, so it
        must be closed instead of deleted once it leaves DRAFT.

        Raises
        ------
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job and is not admin.
            ValidationException: If the job is not in DRAFT status.

        """
        job = await self._repo.get_by_id(job_id)

        if current_user.role != "ADMIN":
            self._check_ownership(job, current_user)

        if job.status != JobStatus.DRAFT.value:
            raise ValidationException(
                "Only draft jobs can be deleted — close published jobs instead"
            )

        await self._repo.delete(job)
        await self._db.commit()

    async def list_jobs(
        self,
        filters: JobFilterParams,
        cursor: str | None = None,
        limit: int = 20,
    ) -> JobListResponse:
        """Return paginated active jobs with optional filters. Public endpoint."""
        result = await self._repo.list_active(filters, cursor, limit)
        return JobListResponse(
            items=[JobResponse.from_job(j, include_interview_brief=False, include_contact_info=False) for j in result["items"]],
            next_cursor=result["next_cursor"],
            count=result["count"],
            total=result["total"],
        )

    async def list_employer_jobs(
        self,
        employer: User,
        cursor: str | None = None,
        limit: int = 20,
        search: str | None = None,
        status_filter: str = "active",
    ) -> JobListResponse:
        """Return paginated jobs owned by the authenticated employer."""
        result = await self._repo.list_by_employer(
            employer.id, cursor, limit, search, status_filter
        )
        return JobListResponse(
            items=[JobResponse.from_job(j, include_interview_brief=True, include_contact_info=True) for j in result["items"]],
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
            items=[JobResponse.from_job(j, include_interview_brief=True, include_contact_info=True) for j in result["items"]],
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
