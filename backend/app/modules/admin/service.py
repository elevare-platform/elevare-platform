"""Business logic for admin operations."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CannotModifyAdminException,
    JobNotFoundError,
    UserNotFoundException,
    ValidationException,
)
from app.modules.admin.repository import AdminRepository
from app.modules.jobs.enums import ModerationStatus
from app.modules.users.enums import UserRole

_VALID_MODERATION_ACTIONS = {
    ModerationStatus.APPROVED.value,
    ModerationStatus.REJECTED.value,
}

_BULK_LIMIT = 100

logger = logging.getLogger(__name__)


class AdminService:
    """Orchestrates admin operations and audit logging."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the service with an async database session."""
        self._db = db
        self._repo = AdminRepository(db)

    # -----------------------------------------------------------------------
    # Users
    # -----------------------------------------------------------------------

    async def list_users(
        self,
        role: str | None = None,
        status: str | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return a paginated list of users with optional role/status/search filters."""
        return await self._repo.list_users(role, status, search, cursor, limit)

    async def get_user_detail(self, user_id: UUID) -> object:
        """Return full user details or raise UserNotFoundException."""
        user = await self._repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        return user

    async def update_user_status(
        self, admin_id: UUID, user_id: UUID, new_status: str
    ) -> object:
        """Update a user's account status and write an audit log entry."""
        user = await self._repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        if user.role == UserRole.ADMIN.value:
            raise CannotModifyAdminException()

        before = user.account_status
        user = await self._repo.set_user_status(user, new_status)
        await self._repo.write_audit_log(
            admin_id=admin_id,
            action="UPDATE_USER_STATUS",
            target_type="user",
            target_id=user_id,
            log_metadata={"before": {"account_status": before}, "after": {"account_status": new_status}},
        )
        await self._db.commit()
        return user

    async def bulk_update_user_status(
        self, admin_id: UUID, user_ids: list[UUID], action: str
    ) -> dict:
        """Update status for multiple users in one operation (max 100)."""
        if len(user_ids) > _BULK_LIMIT:
            raise ValidationException(
                message=f"Bulk operations are limited to {_BULK_LIMIT} records"
            )
        updated = 0
        for user_id in user_ids:
            user = await self._repo.get_user_by_id(user_id)
            if not user or user.role == UserRole.ADMIN.value:
                continue
            before = user.account_status
            await self._repo.set_user_status(user, action)
            await self._repo.write_audit_log(
                admin_id=admin_id,
                action="BULK_UPDATE_USER_STATUS",
                target_type="user",
                target_id=user_id,
                log_metadata={"before": {"account_status": before}, "after": {"account_status": action}},
            )
            updated += 1
        await self._db.commit()
        return {"updated": updated}

    # -----------------------------------------------------------------------
    # Jobs
    # -----------------------------------------------------------------------

    async def list_jobs(
        self,
        status: str | None = None,
        moderation_status: str | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return a paginated list of jobs with optional status/moderation/search filters."""
        from app.modules.jobs.schemas import JobResponse

        result = await self._repo.list_jobs(status, moderation_status, search, cursor, limit)
        result["items"] = [JobResponse.from_job(job) for job in result["items"]]
        return result

    async def moderate_job(
        self, admin_id: UUID, job_id: UUID, action: str, reason: str | None = None
    ) -> object:
        """Approve, reject, or close a job, write an audit log entry, and notify the employer."""
        logger.info(f"\n\n\n\n\n========================Action: {action}=========================\n\n\n\n\n\n")
        action = action.upper()
        logger.info(f"\n\n\n\n\n========================Action: {action}=========================\n\n\n\n\n\n")
        if action not in _VALID_MODERATION_ACTIONS and action != "close":
            raise ValidationException(message=f"Invalid moderation action: {action}")

        job = await self._repo.get_job_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        before = {"moderation_status": job.moderation_status, "status": job.status}

        if action == "close":
            job = await self._repo.set_job_status(job, "CLOSED")
        else:
            job = await self._repo.set_job_moderation_status(job, action)
            from app.modules.applications.tasks import send_job_moderation_email
            send_job_moderation_email.delay(
                job.employer.email,
                str(job.id),
                job.title,
                action,
                reason,
            )

        await self._repo.write_audit_log(
            admin_id=admin_id,
            action=f"MODERATE_JOB_{action.upper()}",
            reason=reason,
            target_type="job",
            target_id=job_id,
            log_metadata={
                "before": before,
                "after": {"moderation_status": job.moderation_status, "status": job.status},
            },
        )
        await self._db.commit()

        from app.modules.jobs.schemas import JobResponse
        return JobResponse.from_job(job)

    async def bulk_update_job_status(
        self, admin_id: UUID, job_ids: list[UUID], action: str
    ) -> dict:
        """Update status for multiple jobs in one operation (max 100)."""
        if len(job_ids) > _BULK_LIMIT:
            raise ValidationException(
                message=f"Bulk operations are limited to {_BULK_LIMIT} records"
            )
        updated = 0
        for job_id in job_ids:
            job = await self._repo.get_job_by_id(job_id)
            if not job:
                continue
            before = job.status
            await self._repo.set_job_status(job, action)
            await self._repo.write_audit_log(
                admin_id=admin_id,
                action="BULK_UPDATE_JOB_STATUS",
                target_type="job",
                target_id=job_id,
                log_metadata={"before": {"status": before}, "after": {"status": action}},
            )
            updated += 1
        await self._db.commit()
        return {"updated": updated}

    # -----------------------------------------------------------------------
    # Applications
    # -----------------------------------------------------------------------

    async def list_applications(
        self,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return a paginated list of all applications platform-wide."""
        return await self._repo.list_applications(status, cursor, limit)

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    async def get_platform_stats(self) -> dict:
        """Return aggregated user, job, and application statistics."""
        return await self._repo.get_platform_stats()

    # -----------------------------------------------------------------------
    # CSV export
    # -----------------------------------------------------------------------

    async def export_applications_csv(self) -> str:
        """Fetch all applications and build a CSV string for download."""
        applications = await self._repo.get_all_applications_for_export()
        return self._repo.build_applications_csv(applications)

    # -----------------------------------------------------------------------
    # Audit log
    # -----------------------------------------------------------------------

    async def list_audit_log(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated audit log entries."""
        return await self._repo.list_audit_log(cursor, limit)
