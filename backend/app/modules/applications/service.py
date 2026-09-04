"""Application service — business logic for job applications."""

import uuid
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import get_email_service
from app.core.exceptions import (
    AlreadyApplied,
    ApplicationNotFound,
    ApplicationWithdrawalError,
    CandidateProfileIncompleteException,
    InvalidStatus,
    JobApplicationEnded,
    PermissionDeniedException,
    ProfileNotFoundException,
)
from app.modules.ai.tasks import compute_match_score_task, score_application_task
from app.modules.applications.enums import ApplicationStatus
from app.modules.applications.repository import ApplicationRepository
from app.modules.applications.schema import (
    ApplicationFilters,
    ApplicationList,
    ApplicationResponse,
)
from app.modules.candidates.repository import CandidateRepository
from app.modules.interview_list.repository import InterviewListRepository
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME, build_full_description
from app.modules.users.enums import UserRole
from app.modules.users.repository import UserRepository


def _job_description(job) -> str:
    """Return the effective job description — structured fields for new jobs, legacy for old."""
    return build_full_description(
        about_the_role=job.about_the_role,
        key_responsibilities=job.key_responsibilities,
        requirements=job.requirements,
        preferred_certifications=job.preferred_certifications,
        technical_competencies=job.technical_competencies,
        what_we_offer=job.what_we_offer,
        legacy_description=job.description,
    )


class ApplicationService:
    """Orchestrates business logic for job application lifecycle management."""

    # Valid status transitions — terminal states have empty sets.
    # A status not in this map is also treated as terminal.
    VALID_TRANSITIONS: dict[str, list[str]] = {
        ApplicationStatus.SUBMITTED.value: [
            ApplicationStatus.REVIEWING.value,
            ApplicationStatus.REJECTED.value,
        ],
        ApplicationStatus.REVIEWING.value: [
            ApplicationStatus.SHORTLISTED.value,
            ApplicationStatus.REJECTED.value,
        ],
        ApplicationStatus.SHORTLISTED.value: [
            ApplicationStatus.INTERVIEWING.value,
            ApplicationStatus.HIRED.value,
            ApplicationStatus.REJECTED.value,
        ],
        ApplicationStatus.INTERVIEWING.value: [
            ApplicationStatus.HIRED.value,
            ApplicationStatus.REJECTED.value,
        ],
        ApplicationStatus.HIRED.value: [],
        ApplicationStatus.REJECTED.value: [],
        ApplicationStatus.WITHDRAWN.value: [],
    }

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the service with an async database session."""
        self._db = db
        self._job_repo = JobRepository(db)
        self._app_repo = ApplicationRepository(db)
        self._candidate_repo = CandidateRepository(db)
        self._user_repo = UserRepository(db)
        self._interview_list_repo = InterviewListRepository(db)

    async def apply_to_job(
        self,
        candidate_id: uuid.UUID,
        job_id: uuid.UUID,
        background_tasks: BackgroundTasks,
        cv_id: uuid.UUID | None = None,
        cover_letter: str | None = None,
    ) -> ApplicationResponse:
        """Create a new application. Fires confirmation emails as background tasks."""
        job = await self._job_repo.get_by_id(job_id)
        candidate = await self._candidate_repo.get_by_user_id(candidate_id)

        if not job:
            from app.core.exceptions import JobNotFoundError

            raise JobNotFoundError()

        if not candidate:
            raise ProfileNotFoundException()

        # Enforce profile completion gate
        if not candidate.is_profile_complete:
            raise CandidateProfileIncompleteException()

        # Enforce application deadline
        if job.application_deadline and job.application_deadline < datetime.now(UTC):
            raise JobApplicationEnded()

        # Guard against duplicate applications
        if await self.has_applied(candidate_id, job_id):
            raise AlreadyApplied()

        # Fall back to the candidate's default CV if none specified
        if cv_id is None:
            cvs = await self._candidate_repo.get_all_cvs(candidate.id)
            for cv in cvs:
                if cv.is_default:
                    cv_id = cv.id
                    break

        application = await self._app_repo.create(
            candidate_id=candidate_id,
            job_id=job_id,
            cv_id=cv_id,
            cover_letter=cover_letter,
        )

        # Reload with all relationships eager-loaded so from_application can
        # safely access job, employer_profile, candidate, candidate_profile
        application = await self._app_repo.get_by_id(application.id)

        # Resolve CV presigned URL for the response
        cv_url = await self._resolve_cv_url(cv_id)

        # Queue emails — these fire after the response is returned.
        # Failures are logged but do not affect the application record.
        job_employer = job.employer
        job_employer_profile = (
            getattr(job_employer, "organization", None) if job_employer else None
        )
        if job_employer_profile and job_employer_profile.company_name:
            confirmation_company_name = job_employer_profile.company_name
        elif job_employer and job_employer.role == "ADMIN":
            confirmation_company_name = PLATFORM_COMPANY_NAME
        else:
            confirmation_company_name = ""

        email_service = get_email_service()
        background_tasks.add_task(
            email_service.send_application_confirmation,
            candidate.user.email,
            job.title,
            confirmation_company_name,
        )
        background_tasks.add_task(
            email_service.send_employer_notification,
            job.employer.email,
            job.title,
            f"{candidate.user.first_name} {candidate.user.last_name}",
            str(job.id),
        )
        await self._db.commit()

        # Queue both scoring tasks after commit — Celery workers run on a
        # separate DB connection and can't see this transaction until it's
        # committed. match_score (deterministic/embedding) and ai_score
        # (LLM reasoning) run independently; both fields coexist on the
        # application.
        compute_match_score_task.delay(str(application.id))
        score_application_task.delay(str(application.id))

        return ApplicationResponse.from_application(application, cv_url=cv_url)

    async def withdraw_application(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> ApplicationResponse:
        """Withdraw an application. Only allowed from submitted or reviewing state."""
        application = await self._app_repo.get_by_id(application_id)
        if not application:
            raise ApplicationNotFound()

        # Ownership check — only the owning candidate can withdraw
        if application.candidate_id != candidate_id:
            raise PermissionDeniedException()

        withdrawable = {
            ApplicationStatus.SUBMITTED.value,
            ApplicationStatus.REVIEWING.value,
        }
        if application.status not in withdrawable:
            raise ApplicationWithdrawalError()

        application = await self._app_repo.update(
            application.id,
            {"status": ApplicationStatus.WITHDRAWN.value},
        )
        await self._db.commit()
        return ApplicationResponse.from_application(application)

    async def get_my_applications(
        self,
        candidate_id: uuid.UUID,
        filters: ApplicationFilters,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ApplicationList:
        """Return paginated applications for the authenticated candidate."""
        from app.modules.interviews.repository import InterviewRepository
        from app.modules.talent_pool.repository import TalentPoolRepository

        paginated = await self._app_repo.get_all_applications_by_candidate(
            candidate_id, filters, cursor, limit
        )

        candidate_profile = await self._candidate_repo.get_by_user_id(candidate_id)
        invited_job_ids = (
            await self._interview_list_repo.list_invited_job_ids(candidate_profile.id)
            if candidate_profile
            else set()
        )

        # Interview.status per job for this candidate — separate from
        # invited_job_ids above, which only says "was ever invited," not
        # whether the interview was actually completed. Needed so the
        # frontend can hide the "Start interview" action once it's done.
        interview_statuses: dict[uuid.UUID, str] = {}
        if candidate_profile:
            talent_pool_profile = await TalentPoolRepository(
                self._db
            ).get_by_candidate_profile_id(candidate_profile.id)
            if talent_pool_profile:
                job_ids = [application.job_id for application in paginated["items"]]
                interview_statuses = await InterviewRepository(
                    self._db
                ).list_statuses_for_profile(talent_pool_profile.id, job_ids)

        items = []
        for application in paginated["items"]:
            cv_url = await self._resolve_cv_url(application.cv_id)
            items.append(
                ApplicationResponse.from_application(
                    application,
                    cv_url=cv_url,
                    interview_invited=application.job_id in invited_job_ids,
                    interview_status=interview_statuses.get(application.job_id),
                )
            )
        return ApplicationList(
            items=items,
            next_cursor=paginated["next_cursor"],
            count=paginated["count"],
            total=paginated["total"],
        )

    async def get_job_applicants(
        self,
        job_id: uuid.UUID,
        current_user_id: uuid.UUID,
        current_user_role: str,
        filters: ApplicationFilters,
        cursor: str | None = None,
        limit: int = 20,
    ) -> ApplicationList:
        """Return paginated applicants for a job.

        Admins can view applicants for any job.
        Employers can only view applicants for jobs they own.
        """
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            from app.core.exceptions import JobNotFoundError

            raise JobNotFoundError()

        # Ownership check — skipped for admins
        if current_user_role != UserRole.ADMIN.value:
            if job.employer_id != current_user_id:
                raise PermissionDeniedException()

        paginated = await self._app_repo.get_job_applicants(
            job_id, filters, cursor, limit
        )

        # Resolve presigned CV URLs for each application concurrently
        items = []
        for application in paginated["items"]:
            cv_url = await self._resolve_cv_url(application.cv_id)
            items.append(
                ApplicationResponse.from_application(application, cv_url=cv_url)
            )

        return ApplicationList(
            items=items,
            next_cursor=paginated["next_cursor"],
            count=paginated["count"],
            total=paginated["total"],
        )

    async def update_application_status(
        self,
        application_id: uuid.UUID,
        new_status: str,
        updated_by: uuid.UUID,
        background_tasks: BackgroundTasks,
    ) -> ApplicationResponse:
        """Transition an application to a new status. Fires a status update email."""
        application = await self._app_repo.get_by_id(application_id)
        if not application:
            raise ApplicationNotFound()

        allowed = self.VALID_TRANSITIONS.get(application.status, [])
        if new_status not in allowed:
            raise InvalidStatus()

        updated = await self._app_repo.update(
            application.id,
            {
                "status": new_status,
                "status_updated_by": updated_by,
                "status_updated_at": datetime.now(UTC),
            },
        )

        email_service = get_email_service()
        background_tasks.add_task(
            email_service.send_status_update,
            application.candidate.email,  # candidate is now a User
            application.job.title,
            new_status,
        )
        await self._db.commit()

        return ApplicationResponse.from_application(updated)

    async def has_applied(self, candidate_id: uuid.UUID, job_id: uuid.UUID) -> bool:
        """Return True if the candidate has an existing application for the given job."""
        result = await self._app_repo.has_applied(candidate_id, job_id)
        await self._db.commit()
        return result is not None

    async def has_applied_batch(
        self, candidate_id: uuid.UUID, job_ids: list[uuid.UUID]
    ) -> dict[str, bool]:
        """Return a map of job_id → has_applied for the given list of job IDs."""
        applied_set = await self._app_repo.has_applied_batch(candidate_id, job_ids)
        return {str(jid): (jid in applied_set) for jid in job_ids}

    async def _resolve_cv_url(self, cv_id: uuid.UUID | None) -> str | None:
        """Generate a presigned URL for the CV attached to an application."""
        if cv_id is None:
            return None
        cv = await self._candidate_repo.get_cv(cv_id)
        if cv is None:
            return None
        from app.core.storage import get_storage_service

        storage = get_storage_service()
        return await storage.generate_presigned_url(cv.key, expires_seconds=900)
