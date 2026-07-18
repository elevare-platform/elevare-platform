"""Business logic for the talent pool — CV submission, listing, promotion, and scoring."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobNotFoundError,
    PermissionDeniedException,
    SubmissionNotFound,
    ValidationException,
)
from app.modules.ai.cv_parsing_service import CVParsingService
from app.modules.ai.repository import AIRepository
from app.modules.ai.tasks import score_talent_pool_profile_task
from app.modules.auth.service import AuthService
from app.modules.candidates.enums import VisibilityStatus
from app.modules.jobs.repository import JobRepository
from app.modules.talent_pool.enums import TalentPoolStatus
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.repository import TalentPoolRepository
from app.modules.talent_pool.schema import (
    TalentMatchListResponse,
    TalentPoolProfileResponse,
    TalentPoolPromoteResponse,
    TalentPoolStatusUpdateRequest,
    TalentPoolSubmitRequest,
)
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


async def resolve_match_display_fields(
    db: AsyncSession,
    profile: TalentPoolProfiles,
    employer_id: uuid.UUID,
    override_mask: bool = False,
) -> dict:
    """Resolve display fields for a talent pool profile, respecting candidate visibility.

    Works for both self-registered candidates (prefers CandidateProfile data)
    and sourced-only CVs (falls back to parsed_submission data).

    ``override_mask=True`` reveals the name regardless of visibility — used
    once the candidate has ACCEPTED an introduction request from this
    employer, which is itself a candidate-granted exception to their
    visibility setting.
    """
    from app.modules.candidates.repository import CandidateRepository

    parsed_current_title: str | None = None
    parsed_profession: str | None = None
    parsed_name: str | None = None
    parsed_skills: list[str] = []
    parsed_location: str | None = None
    parsed_years: int | None = None

    # Source data from parsed submission (works for both sourced and registered profiles)
    submission = profile.parsed_submission
    if submission and submission.parsed_data:
        pd = submission.parsed_data
        parsed_current_title = pd.get("current_title")
        parsed_profession = pd.get("profession")
        parsed_name = pd.get("full_name") or (
            f"{pd.get('first_name', '')} {pd.get('last_name', '')}".strip() or None
        )
        parsed_skills = pd.get("skills") or []
        parsed_years = pd.get("years_experience")

    # For self-registered candidates, prefer structured profile data
    candidate_profile = profile.candidate_profile
    if candidate_profile:
        parsed_location = candidate_profile.location
        parsed_years = candidate_profile.years_of_experience or parsed_years
        parsed_skills = candidate_profile.skills or parsed_skills
        if candidate_profile.user:
            u = candidate_profile.user
            visibility = candidate_profile.visibility
            if override_mask:
                parsed_name = f"{u.first_name} {u.last_name}".strip()
            elif visibility == VisibilityStatus.PRIVATE.value:
                parsed_name = None
            elif visibility == VisibilityStatus.APPLIED_ONLY.value:
                candidate_repo = CandidateRepository(db)
                has_applied = await candidate_repo.candidate_has_applied_to_employer(
                    candidate_profile_id=candidate_profile.id,
                    employer_id=employer_id,
                )
                parsed_name = (
                    f"{u.first_name} {u.last_name}".strip() if has_applied else None
                )
            else:
                # PUBLIC — always show
                parsed_name = f"{u.first_name} {u.last_name}".strip()

    return {
        "name": parsed_name,
        "current_title": parsed_current_title,
        "profession": parsed_profession,
        "skills": parsed_skills[:5],
        "location": parsed_location,
        "years_of_experience": parsed_years,
    }


class TalentPoolService:
    """Orchestrates talent pool CV submissions, scoring, and candidate promotion."""

    def __init__(self, db: AsyncSession, cv_service: CVParsingService):
        """Initialise with a database session and a CVParsingService dependency."""
        self._db = db
        self._cv_service = cv_service
        self._repo = TalentPoolRepository(db)
        self._ai_repo = AIRepository(db)
        self._user_repo = UserRepository(db)
        self._auth_service = AuthService(db)

    async def _enrich(
        self, profile, response: TalentPoolProfileResponse
    ) -> TalentPoolProfileResponse:
        """Populate candidate_name, email, and current_title from parsed CV data."""
        if profile.parsed_submission_id:
            submission = await self._ai_repo.get_submission_by_id(
                profile.parsed_submission_id
            )
            if submission and submission.parsed_data:
                data = submission.parsed_data
                full_name = data.get("full_name") or (
                    f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
                    or None
                )
                response.candidate_name = full_name
                response.candidate_email = data.get("email")
                response.candidate_current_title = data.get("current_title")
        return response

    async def submit(
        self,
        file: bytes,
        filename: str,
        data: TalentPoolSubmitRequest,
        current_user: User,
    ):
        """Submit a single CV into the talent pool and queue parsing/scoring."""
        submission = await self._cv_service.submit_cv_for_parsing(
            uploaded_by=current_user, file=file, filename=filename
        )

        # Deduplication — same CV content already exists against this job
        existing = await self._repo.get_by_cv_hash(
            submission.cv_text_hash, data.sourced_for_job_id
        )
        if existing:
            response = TalentPoolProfileResponse.model_validate(existing)
            return await self._enrich(existing, response)

        # Create talent pool profile
        profile = await self._repo.create(
            {
                "parsed_submission_id": submission.id,
                "source": data.source,
                "source_note": data.source_note,
                "sourced_for_job_id": data.sourced_for_job_id,
                "added_by": current_user.id,
                "status": TalentPoolStatus.NEW.value,
            }
        )

        if data.sourced_for_job_id:
            score_talent_pool_profile_task.delay(str(profile.id))

        await self._db.commit()
        response = TalentPoolProfileResponse.model_validate(profile)
        return await self._enrich(profile, response)

    async def submit_batch(
        self,
        files: list[tuple[bytes, str]],  # list of (file_bytes, filename)
        data: TalentPoolSubmitRequest,
        current_user: User,
    ) -> list[dict]:
        """Upload multiple CVs in one request. Returns per-file status."""
        results = []
        for file_bytes, filename in files:
            try:
                submission = await self._cv_service.submit_cv_for_parsing(
                    uploaded_by=current_user,
                    file=file_bytes,
                    filename=filename,
                )
                # Deduplication — skip if same CV content+job already exists
                existing = await self._repo.get_by_cv_hash(
                    submission.cv_text_hash, data.sourced_for_job_id
                )
                if existing:
                    results.append(
                        {
                            "filename": filename,
                            "status": "duplicate",
                            "profile_id": str(existing.id),
                            "submission_id": str(submission.id),
                        }
                    )
                    continue

                profile = await self._repo.create(
                    {
                        "parsed_submission_id": submission.id,
                        "source": data.source,
                        "source_note": data.source_note,
                        "sourced_for_job_id": data.sourced_for_job_id,
                        "added_by": current_user.id,
                        "status": TalentPoolStatus.NEW.value,
                    }
                )
                if data.sourced_for_job_id:
                    score_talent_pool_profile_task.delay(str(profile.id))
                await self._db.commit()
                results.append(
                    {
                        "filename": filename,
                        "status": "queued",
                        "profile_id": str(profile.id),
                        "submission_id": str(submission.id),
                    }
                )
            except Exception as e:
                logger.error("Batch submit failed for %s: %s", filename, e)
                results.append(
                    {"filename": filename, "status": "failed", "error": str(e)}
                )
        return results

    async def list_profiles(
        self,
        status: str | None,
        source: str | None,
        job_id: uuid.UUID | None,
        cursor: str | None,
        limit: int,
        current_user,
    ) -> dict:
        """Return paginated talent pool profiles, enriched with parsed CV data."""
        is_admin = current_user.role == UserRole.ADMIN.value
        result = await self._repo.list(
            status=status,
            source=source,
            job_id=job_id,
            cursor=cursor,
            limit=limit,
            viewer_id=current_user.id,
            is_admin=is_admin,
        )
        enriched = []
        for profile in result["items"]:
            resp = TalentPoolProfileResponse.model_validate(profile)
            resp = await self._enrich(profile, resp)
            enriched.append(resp)
        result["items"] = enriched
        return result

    async def get_profile(self, id: uuid.UUID) -> TalentPoolProfileResponse:
        """Fetch a single talent pool profile by ID, or raise SubmissionNotFound."""
        profile = await self._repo.get_by_id(id)
        if not profile:
            raise SubmissionNotFound()
        response = TalentPoolProfileResponse.model_validate(profile)
        return await self._enrich(profile, response)

    async def update_status(
        self,
        profile_id: uuid.UUID,
        data: TalentPoolStatusUpdateRequest,
    ) -> TalentPoolProfileResponse:
        """Update the status of a talent pool profile.

        Sends a shortlist notification email when status transitions to SHORTLISTED.
        Raises ValidationException for disallowed status values (PROMOTED/PROMOTED_PENDING).
        """
        allowed_status = {s.value for s in TalentPoolStatus} - {
            TalentPoolStatus.PROMOTED.value,
            TalentPoolStatus.PROMOTED_PENDING.value,
        }
        if data.status not in allowed_status:
            raise ValidationException(f"Invalid status. Allowed: {allowed_status}")

        profile = await self._repo.update(profile_id, {"status": data.status})
        if not profile:
            raise SubmissionNotFound()

        # Send email notification when shortlisted, if email is available
        if data.status == TalentPoolStatus.SHORTLISTED.value:
            try:
                candidate_email: str | None = None

                # Try parsed submission first (sourced CVs and registered candidates who uploaded)
                if profile.parsed_submission_id:
                    submission = await self._ai_repo.get_submission_by_id(
                        profile.parsed_submission_id
                    )
                    candidate_email = (
                        (submission.parsed_data or {}).get("email")
                        if submission
                        else None
                    )

                # Fallback — self-registered candidate with no parsed submission
                if not candidate_email and profile.candidate_profile_id:
                    from sqlalchemy import select

                    from app.modules.candidates.models import CandidateProfile
                    from app.modules.users.models import User as UserModel

                    result = await self._db.execute(
                        select(UserModel.email)
                        .join(
                            CandidateProfile, CandidateProfile.user_id == UserModel.id
                        )
                        .where(CandidateProfile.id == profile.candidate_profile_id)
                    )
                    candidate_email = result.scalar_one_or_none()

                if candidate_email:
                    from app.core.config import settings
                    from app.core.email import get_email_service

                    email_service = get_email_service()
                    if settings.email_stub_mode:
                        logger.info(
                            "Talent pool shortlist notification → %s", candidate_email
                        )
                    else:
                        await email_service.send_status_update(
                            candidate_email=candidate_email,
                            job_title="a role",
                            new_status="shortlisted",
                        )
            except Exception:
                logger.warning(
                    "Failed to send shortlist notification for profile %s", profile_id
                )

        await self._db.commit()
        return TalentPoolProfileResponse.model_validate(profile)

    async def promote(
        self,
        profile_id: uuid.UUID,
        current_user,
    ) -> TalentPoolPromoteResponse:
        """Begin promotion — send an invite to the candidate.

        Returns a conflict response if an active user already exists for
        the parsed email. The application is created only after the
        candidate confirms via the invite link.
        """
        profile = await self._repo.get_by_id(profile_id)
        if not profile:
            raise SubmissionNotFound()

        # Load Parsed data to get email
        submission = await self._ai_repo.get_submission_by_id(
            profile.parsed_submission_id
        )
        if not submission or not submission.parsed_data:
            raise ValidationException("Parsed data not available.")

        email = (submission.parsed_data or {}).get("email")
        if not email:
            raise ValidationException(
                "Parsed CV has no email address — cannot send invite"
            )

        existing_user = await self._user_repo.get_user_by_email(email)
        if existing_user and existing_user.account_status == AccountStatus.ACTIVE.value:
            return TalentPoolPromoteResponse(
                message="A user with this email already exists and is active. Manual review required.",
                status="conflict",
                conflict_email=email,
            )

        # Trigger invite via existing auth flow
        await self._auth_service.create_invite(
            email,
            role=UserRole.CANDIDATE.value,
            admin_id=current_user.id,
        )

        logger.info("Talent pool promote invite sent to %s", email)

        await self._repo.update(
            profile_id,
            {
                "status": TalentPoolStatus.PROMOTED_PENDING.value,
                "last_invite_sent_at": datetime.now(UTC),
            },
        )
        await self._db.commit()

        return TalentPoolPromoteResponse(
            message="Invite sent. Profile will be promoted once candidate confirms.",
            status="invite_sent",
        )

    async def score_against_job(
        self,
        job_id: uuid.UUID,
    ) -> dict:
        """Queue scoring for all unscored pipeline profiles against a given job.

        Only fires for profiles that have a parsed_submission_id.
        Hash-based idempotency in the task prevents redundant LLM calls.
        """
        from app.modules.ai.tasks import score_talent_pool_profile_task
        from app.modules.jobs.repository import JobRepository

        job_repo = JobRepository(self._db)
        job = await job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        # Get all profiles that have a parsed submission (uploaded CVs, not self-registered)
        # and are sourced for this job or have no job yet
        profiles = await self._repo.list_unscored_for_job(job_id)
        queued = 0
        for profile in profiles:
            score_talent_pool_profile_task.delay(str(profile.id), str(job_id))
            queued += 1

        return {"queued": queued, "job_id": str(job_id)}

    async def get_job_matches(
        self,
        job_id: uuid.UUID,
        employer_id: uuid.UUID,
        limit: int = 20,
    ) -> "TalentMatchListResponse":
        """Return AI-matched talent pool profiles for a job, ranked by embedding similarity."""
        from app.modules.applications.repository import ApplicationRepository
        from app.modules.talent_pool.schema import (
            TalentMatchListResponse,
            TalentMatchResponse,
        )

        job_repo = JobRepository(self._db)
        application_repo = ApplicationRepository(self._db)

        job = await job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        if job.employer_id != employer_id:
            raise PermissionDeniedException()

        if job.job_embedding is None:
            raise ValidationException(
                "Job embedding not yet generated — check back shortly."
            )

        user_ids = await application_repo.get_user_ids_for_job(job_id)

        matches = await self._repo.find_matches_for_job(
            job_embedding=job.job_embedding,
            exclude_user_ids=user_ids,
            limit=limit,
        )

        items: list[TalentMatchResponse] = []
        for profile, distance in matches:
            fields = await resolve_match_display_fields(self._db, profile, employer_id)
            items.append(
                TalentMatchResponse.from_match(
                    profile=profile,
                    distance=distance,
                    candidate_name=fields["name"],
                    current_title=fields["current_title"],
                    profession=fields["profession"],
                    years_of_experience=fields["years_of_experience"],
                    location=fields["location"],
                    top_skills=fields["skills"],
                )
            )

        return TalentMatchListResponse(
            items=items,
            count=len(items),
            job_id=job_id,
        )
