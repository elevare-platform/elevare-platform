"""Data-access layer for admin operations."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pagination import paginate_cursor
from app.modules.admin.models import AuditLog
from app.modules.applications.models import Application
from app.modules.jobs.enums import JobStatus, ModerationStatus
from app.modules.jobs.models import Job
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import User


class AdminRepository:
    """Database queries for admin service operations."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session."""
        self._db = db

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
        """Return a paginated cursor result of users with optional filters."""
        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role)
        if status:
            stmt = stmt.where(User.account_status == status)
        if search:
            term = f"%{search}%"
            stmt = stmt.where(
                or_(User.email.ilike(term), User.first_name.ilike(term), User.last_name.ilike(term))
            )
        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Fetch a user by UUID with employer and candidate profiles loaded."""
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.employer_profile),
                selectinload(User.candidate_profile),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_user_status(self, user: User, status: str) -> User:
        """Update a user's account_status and flush the session."""
        user.account_status = status
        await self._db.flush()
        return user

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
        """Return a paginated cursor result of jobs with optional filters."""
        stmt = select(Job).options(
            selectinload(Job.employer).selectinload(User.employer_profile)
        )
        if status:
            stmt = stmt.where(Job.status == status)
        if moderation_status:
            stmt = stmt.where(Job.moderation_status == moderation_status)
        if search:
            term = f"%{search}%"
            stmt = stmt.where(
                or_(Job.title.ilike(term), Job.location.ilike(term))
            )
        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def get_job_by_id(self, job_id: UUID) -> Job | None:
        """Fetch a job by UUID with employer and employer_profile loaded."""
        stmt = (
            select(Job)
            .where(Job.id == job_id)
            .options(selectinload(Job.employer).selectinload(User.employer_profile))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def set_job_moderation_status(self, job: Job, moderation_status: str) -> Job:
        """Set a job's moderation_status and return the job to DRAFT if rejected."""
        job.moderation_status = moderation_status
        if moderation_status == ModerationStatus.REJECTED.value:
            # Return to DRAFT so employer can edit and resubmit — CLOSED is permanent
            job.status = JobStatus.DRAFT.value
        await self._db.flush()
        return job

    async def set_job_status(self, job: Job, status: str) -> Job:
        """Set a job's status field directly."""
        job.status = status
        await self._db.flush()
        return job

    # -----------------------------------------------------------------------
    # Applications
    # -----------------------------------------------------------------------

    async def list_applications(
        self,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return a paginated cursor result of all applications platform-wide."""
        stmt = select(Application).options(
            selectinload(Application.candidate),
            selectinload(Application.job),
        )
        if status:
            stmt = stmt.where(Application.status == status)
        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def get_all_applications_for_export(self) -> list[Application]:
        """Fetch all applications with employer profile data for CSV export."""
        stmt = select(Application).options(
            selectinload(Application.candidate),
            selectinload(Application.job).selectinload(Job.employer).selectinload(User.employer_profile),
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    async def get_platform_stats(self) -> dict:
        """Return aggregated counts for users, jobs, and applications."""
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

        # Users — single query with FILTER
        user_stats = await self._db.execute(
            select(
                func.count().label("total"),
                func.count().filter(User.role == UserRole.CANDIDATE.value).label("candidates"),
                func.count().filter(User.role == UserRole.EMPLOYER.value).label("employers"),
                func.count().filter(User.role == UserRole.ADMIN.value).label("admins"),
                func.count().filter(
                    User.account_status == AccountStatus.PENDING_VERIFICATION.value
                ).label("pending_verification"),
                func.count().filter(User.created_at >= thirty_days_ago).label("new_last_30_days"),
            ).select_from(User)
        )
        users = user_stats.mappings().one()

        # Jobs — single query with FILTER
        job_stats = await self._db.execute(
            select(
                func.count().label("total"),
                func.count().filter(Job.status == JobStatus.ACTIVE.value).label("active"),
                func.count().filter(Job.status == JobStatus.DRAFT.value).label("draft"),
                func.count().filter(Job.status == JobStatus.CLOSED.value).label("closed"),
                func.count().filter(
                    Job.moderation_status == ModerationStatus.PENDING.value
                ).label("pending_moderation"),
                func.count().filter(Job.created_at >= thirty_days_ago).label("new_last_30_days"),
            ).select_from(Job)
        )
        jobs = job_stats.mappings().one()

        # Applications — single query with FILTER
        from app.modules.applications.enums import ApplicationStatus
        app_stats = await self._db.execute(
            select(
                func.count().label("total"),
                func.count().filter(
                    Application.status == ApplicationStatus.SUBMITTED.value
                ).label("submitted"),
                func.count().filter(
                    Application.status == ApplicationStatus.REVIEWING.value
                ).label("reviewing"),
                func.count().filter(
                    Application.status == ApplicationStatus.SHORTLISTED.value
                ).label("shortlisted"),
                func.count().filter(
                    Application.status == ApplicationStatus.HIRED.value
                ).label("hired"),
                func.count().filter(
                    Application.status == ApplicationStatus.REJECTED.value
                ).label("rejected"),
                func.count().filter(
                    Application.created_at >= thirty_days_ago
                ).label("new_last_30_days"),
            ).select_from(Application)
        )
        applications = app_stats.mappings().one()

        return {
            "users": dict(users),
            "jobs": dict(jobs),
            "applications": dict(applications),
        }

    # -----------------------------------------------------------------------
    # Audit log
    # -----------------------------------------------------------------------

    async def write_audit_log(
        self,
        admin_id: UUID,
        action: str,
        target_type: str,
        target_id: UUID,
        log_metadata: dict | None = None,
        reason: str | None = None,
    ) -> AuditLog:
        """Create and flush an AuditLog entry for the given admin action."""
        entry = AuditLog(
            admin_id=admin_id,
            action=action,
            reason=reason,
            target_type=target_type,
            target_id=target_id,
            log_metadata=log_metadata or {},
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def list_audit_log(
        self,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated audit log entries ordered by most recent first."""
        stmt = (
            select(AuditLog)
            .options(selectinload(AuditLog.admin))
            .order_by(AuditLog.created_at.desc())
        )
        return await paginate_cursor(stmt, self._db, cursor, limit)

    # -----------------------------------------------------------------------
    # CSV export
    # -----------------------------------------------------------------------

    def build_applications_csv(self, applications: list[Application]) -> str:
        """Build a CSV string from a list of Application ORM objects."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "application_id", "candidate_name", "candidate_email",
            "job_title", "company_name", "status", "applied_date", "status_updated_date",
        ])
        for app in applications:
            company = ""
            if app.job and app.job.employer and app.job.employer.employer_profile:
                company = app.job.employer.employer_profile.company_name or ""
            writer.writerow([
                str(app.id),
                f"{app.candidate.first_name} {app.candidate.last_name}" if app.candidate else "",
                app.candidate.email if app.candidate else "",
                app.job.title if app.job else "",
                company,
                app.status,
                app.created_at.isoformat() if app.created_at else "",
                app.status_updated_at.isoformat() if app.status_updated_at else "",
            ])
        return output.getvalue()
