"""Business logic for admin operations."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CannotModifyAdminException,
    DocumentNotFoundError,
    JobNotFoundError,
    ProfileNotFoundException,
    UserNotFoundException,
    ValidationException,
)
from app.core.storage import StorageService
from app.modules.admin.repository import AdminRepository
from app.modules.employer.enums import KYCStatus
from app.modules.jobs.enums import ModerationStatus
from app.modules.users.enums import UserRole

_VALID_MODERATION_ACTIONS = {
    ModerationStatus.APPROVED.value,
    ModerationStatus.REJECTED.value,
}

_VALID_KYC_ACTIONS = {
    KYCStatus.APPROVED.value,
    KYCStatus.REJECTED.value,
}

_BULK_LIMIT = 100

logger = logging.getLogger(__name__)


class AdminService:
    """Orchestrates admin operations and audit logging."""

    def __init__(self, db: AsyncSession, storage: StorageService | None = None) -> None:
        """Initialise the service with an async database session."""
        self._db = db
        self._repo = AdminRepository(db)
        self._storage = storage

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
        from app.modules.admin.schemas import AdminUserResponse

        result = await self._repo.list_users(role, status, search, cursor, limit)
        result["items"] = [AdminUserResponse.model_validate(u) for u in result["items"]]
        return result

    async def get_user_detail(self, user_id: UUID) -> object:
        """Return full user details or raise UserNotFoundException."""
        from app.modules.admin.schemas import AdminUserResponse

        user = await self._repo.get_user_by_id(user_id)
        if not user:
            raise UserNotFoundException()
        return AdminUserResponse.model_validate(user)

    async def update_user_status(
        self, admin_id: UUID, user_id: UUID, new_status: str
    ) -> object:
        """Update a user's account status and write an audit log entry."""
        from app.modules.admin.schemas import AdminUserResponse

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
            log_metadata={
                "before": {"account_status": before},
                "after": {"account_status": new_status},
            },
        )
        await self._db.commit()
        return AdminUserResponse.model_validate(user)

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
                log_metadata={
                    "before": {"account_status": before},
                    "after": {"account_status": action},
                },
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

        result = await self._repo.list_jobs(
            status, moderation_status, search, cursor, limit
        )
        result["items"] = [JobResponse.from_job(job) for job in result["items"]]
        return result

    async def moderate_job(
        self, admin_id: UUID, job_id: UUID, action: str, reason: str | None = None
    ) -> object:
        """Approve, reject, or close a job, write an audit log entry, and notify the employer."""
        logger.info(
            f"\n\n\n\n\n========================Action: {action}=========================\n\n\n\n\n\n"
        )
        action = action.upper()
        logger.info(
            f"\n\n\n\n\n========================Action: {action}=========================\n\n\n\n\n\n"
        )
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
                "after": {
                    "moderation_status": job.moderation_status,
                    "status": job.status,
                },
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
                log_metadata={
                    "before": {"status": before},
                    "after": {"status": action},
                },
            )
            updated += 1
        await self._db.commit()
        return {"updated": updated}

    # -----------------------------------------------------------------------
    # Employer KYC
    # -----------------------------------------------------------------------

    async def list_kyc_submissions(
        self,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return a paginated list of employer KYC submissions."""
        from app.modules.admin.schemas import AdminKYCEmployerResponse

        result = await self._repo.list_kyc_submissions(status, cursor, limit)
        result["items"] = [
            AdminKYCEmployerResponse.from_profile(p) for p in result["items"]
        ]
        return result

    async def get_kyc_document_url(self, document_id: UUID) -> str:
        """Generate a presigned URL so an admin can review a KYC document."""
        from app.modules.employer.repository import EmployerRepository

        emp_repo = EmployerRepository(self._db)
        doc = await emp_repo.get_kyc_document(document_id)
        if not doc:
            raise DocumentNotFoundError()
        return await self._storage.generate_presigned_url(doc.key, 60 * 15)

    async def moderate_kyc(
        self,
        admin_id: UUID,
        employer_profile_id: UUID,
        action: str,
        reason: str | None = None,
    ) -> object:
        """Approve or reject an employer's KYC submission and write an audit log entry."""
        from app.modules.admin.schemas import AdminKYCEmployerResponse
        from app.modules.employer.repository import EmployerRepository

        action = action.upper()
        if action not in _VALID_KYC_ACTIONS:
            raise ValidationException(message=f"Invalid KYC action: {action}")

        profile = await self._repo.get_employer_profile_by_id(employer_profile_id)
        if not profile:
            raise ProfileNotFoundException()

        before = profile.kyc_status
        emp_repo = EmployerRepository(self._db)
        profile = await emp_repo.set_kyc_status(profile, action, reason)

        await self._repo.write_audit_log(
            admin_id=admin_id,
            action=f"MODERATE_KYC_{action}",
            reason=reason,
            target_type="employer_profile",
            target_id=profile.id,
            log_metadata={
                "before": {"kyc_status": before},
                "after": {"kyc_status": profile.kyc_status},
            },
        )
        await self._db.commit()

        # Send email notification to employer
        from app.core.email import get_email_service

        email_service = get_email_service()
        employer_email = profile.user.email
        company_name = profile.company_name

        if action == KYCStatus.REJECTED.value:
            await email_service.send_kyc_rejection(employer_email, company_name, reason)
        elif action == KYCStatus.APPROVED.value:
            await email_service.send_kyc_approved(employer_email, company_name)

        return AdminKYCEmployerResponse.from_profile(profile)
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
        from app.modules.admin.schemas import AdminApplicationResponse

        result = await self._repo.list_applications(status, cursor, limit)
        result["items"] = [
            AdminApplicationResponse.from_application(a) for a in result["items"]
        ]
        return result

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
    # Credits
    # -----------------------------------------------------------------------

    async def grant_employer_credits(
        self,
        admin_id: UUID,
        employer_id: UUID,
        amount: int,
        reason: str | None = None,
    ) -> dict:
        """Grant credits to an employer, write an audit log entry, and commit."""
        from app.modules.credits.service import CreditsService

        credits_service = CreditsService(self._db)
        new_balance = await credits_service.grant(
            employer_id=employer_id,
            amount=amount,
        )
        await self._repo.write_audit_log(
            admin_id=admin_id,
            action="GRANT_CREDITS",
            target_type="employer",
            target_id=employer_id,
            log_metadata={
                "amount": amount,
                "reason": reason,
                "new_balance": new_balance,
            },
        )
        await self._db.commit()
        return {"employer_id": str(employer_id), "balance": new_balance}

    # -----------------------------------------------------------------------
    # Audit log
    # -----------------------------------------------------------------------

    async def list_audit_log(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated audit log entries."""
        from app.modules.admin.schemas import AuditLogResponse

        result = await self._repo.list_audit_log(cursor, limit)
        result["items"] = [AuditLogResponse.model_validate(e) for e in result["items"]]
        return result
