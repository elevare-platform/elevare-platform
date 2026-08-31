"""Business logic for the talent pool — CV submission, listing, promotion, and scoring."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobNotFoundError,
    PermissionDeniedException,
    ProfileNotFoundException,
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

# Starter orgs can source and store unlimited CVs into the pool, but can
# only ever browse this many of them — a visibility cap, not a storage cap.
# Uploading past this point still works; paging/viewing past it doesn't.
STARTER_TALENT_POOL_VISIBLE_LIMIT = 5

# Below this blended score, a match is hidden rather than shown at a
# technically-top-N-but-obviously-irrelevant percentage. Initial estimate —
# tune after observing real score distributions post-launch.
_MIN_SIMILARITY_SCORE = 40

# How many candidates over the requested limit to pull by raw embedding
# distance before re-ranking by the blended (embedding + skill-overlap)
# score. Needed because skill overlap can promote a candidate who wasn't
# in the top-N by embedding distance alone — over-fetch so re-ranking can
# actually change who shows up, not just the displayed number.
_MATCH_OVERFETCH_MULTIPLIER = 4
_MATCH_OVERFETCH_CAP = 100


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
    parsed_summary: str | None = None

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
        parsed_summary = pd.get("summary")

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
        # Full list, not truncated — callers need the complete set for
        # skill-overlap scoring against job.required_skills. Truncate to
        # top_skills for display separately.
        "skills": parsed_skills,
        "location": parsed_location,
        "years_of_experience": parsed_years,
        "summary": parsed_summary,
    }


async def get_top_matches_for_job(
    db: AsyncSession,
    job,
    employer_id: uuid.UUID,
    limit: int = 20,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> list[tuple[TalentPoolProfiles, int, list[str]]]:
    """Return the top N talent pool profiles for a job using the full blended scoring.

    Replicates the exact logic from get_job_matches (overfetch → embedding score
    * skill modulator → floor filter → re-rank) so the Celery task and the API
    endpoint always agree on which profiles are top matches.

    Returns list of (profile, final_score, matched_skills) sorted by final_score descending.
    matched_skills is the intersection of candidate skills and job.required_skills (max 3).
    """
    from app.modules.ai.scoring_service import compute_skill_overlap_modulator

    repo = TalentPoolRepository(db)
    fetch_limit = min(limit * _MATCH_OVERFETCH_MULTIPLIER, _MATCH_OVERFETCH_CAP)
    matches = await repo.find_matches_for_job(
        job_embedding=job.job_embedding,
        employer_id=employer_id,
        exclude_user_ids=exclude_user_ids or [],
        limit=fetch_limit,
    )

    job_skills_lower = {s.lower() for s in (job.required_skills or [])}

    scored: list[tuple[TalentPoolProfiles, int, list[str]]] = []
    for profile, distance in matches:
        fields = await resolve_match_display_fields(db, profile, employer_id)
        embedding_score = max(0, min(100, round((1 - distance) * 100)))
        modulator = compute_skill_overlap_modulator(
            fields["skills"], job.required_skills
        )
        final_score = max(0, min(100, round(embedding_score * modulator)))
        if final_score >= _MIN_SIMILARITY_SCORE:
            matched = [s for s in fields["skills"] if s.lower() in job_skills_lower][:3]
            scored.append((profile, final_score, matched))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


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
                response.summary = data.get("summary")
                response.skills = data.get("skills") or []
        if profile.override_email:
            response.candidate_email = profile.override_email
        return response

    async def _can_auto_score(self, current_user: User) -> bool:
        """Whether uploads for this org may trigger LLM scoring as a
        side effect. Scoring is a paid-tier feature (see the gates on
        POST /score-against-job and POST /{id}/score) — without this check,
        attaching a job to an upload would silently score it for free and
        bypass those gates entirely.
        """
        if current_user.role == UserRole.ADMIN.value:
            return True
        from app.modules.billing.service import BillingService

        plan = await BillingService(self._db).get_effective_plan(
            current_user.organization_id
        )
        return plan.code != "starter"

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

        if data.sourced_for_job_id and await self._can_auto_score(current_user):
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
        can_auto_score = await self._can_auto_score(current_user)
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
                if data.sourced_for_job_id and can_auto_score:
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

        capped = False
        if not is_admin:
            from app.modules.billing.service import BillingService

            plan = await BillingService(self._db).get_effective_plan(
                current_user.organization_id
            )
            if plan.code == "starter":
                capped = True
                cursor = None  # Starter never pages past the visible cap
                limit = min(limit, STARTER_TALENT_POOL_VISIBLE_LIMIT)

        result = await self._repo.list(
            status=status,
            source=source,
            job_id=job_id,
            cursor=cursor,
            limit=limit,
            viewer_id=current_user.id,
            is_admin=is_admin,
        )
        if capped:
            result["items"] = result["items"][:STARTER_TALENT_POOL_VISIBLE_LIMIT]
            result["next_cursor"] = None

        from app.modules.introductions.repository import IntroductionRepository

        intro_repo = IntroductionRepository(self._db)

        enriched = []
        for profile in result["items"]:
            resp = TalentPoolProfileResponse.model_validate(profile)
            resp = await self._enrich(profile, resp)

            is_owner = profile.added_by == current_user.id
            if profile.candidate_profile_id is not None:
                resp.ownership = "self_registered"
                resp.has_cv_access = True
            elif is_owner:
                resp.ownership = "own_sourced"
                resp.has_cv_access = True
            elif is_admin:
                resp.ownership = "admin_sourced"
                resp.has_cv_access = True
            else:
                resp.ownership = "admin_sourced"
                resp.has_cv_access = await intro_repo.has_accepted_introduction(
                    employer_id=current_user.id, talent_pool_profile_id=profile.id
                )

            enriched.append(resp)
        result["items"] = enriched
        return result

    async def get_profile(
        self,
        id: uuid.UUID,
        current_user: User,
        job_id: uuid.UUID | None = None,
    ) -> TalentPoolProfileResponse:
        """Fetch a single talent pool profile by ID — sourced CVs only.

        This backs ``SourcedCvModal``, which by design only shows sourced
        (no-login) candidates. Self-registered candidates are viewed through
        ``GET /api/v1/candidates/{id}``, which already enforces the
        candidate's visibility setting — so a profile with
        ``candidate_profile_id`` set has no business being fetched here at
        all.

        Access to the sourced candidate's identity, CV, and AI assessment is
        only granted if the requester sourced it themselves, is an admin, or
        has an ACCEPTED introduction for this candidate (from any job — an
        acceptance is the candidate agreeing to be introduced to this
        employer, not to one specific posting). Everyone else gets a 403,
        not a partial/empty profile — there is no legitimate "preview" tier
        for a sourced CV the employer hasn't been granted access to.

        ``ai_score``/``ai_fit_summary``/etc. are a single set of columns per
        profile — computed against whichever job most recently triggered
        scoring, not per job viewed from. Without a ``job_id`` (e.g. the
        job-less Candidate Search flow) there is no job to judge relevance
        against, so the assessment is never included. With a ``job_id``, it's
        only included if ``ai_score_job_hash`` still matches that job's
        current scoring inputs — otherwise the stored assessment is stale
        (computed against a different job) and would be actively misleading
        to show as if it were about this one.
        """
        from app.core.storage import get_storage_service

        profile = await self._repo.get_by_id(id)
        if not profile:
            raise SubmissionNotFound()

        await self._check_sourced_cv_access(profile, current_user)

        response = TalentPoolProfileResponse.model_validate(profile)
        response = await self._enrich(profile, response)

        # Only surface the AI assessment if it's verifiably about the job
        # currently being viewed from — never guess, never show it
        # unqualified.
        assessment_is_current_for_job = False
        if job_id and profile.ai_score_job_hash:
            job = await JobRepository(self._db).get_by_id(job_id)
            if job:
                from app.modules.ai.scoring_service import hash_job_scoring_inputs
                from app.modules.jobs.schemas import build_full_description

                current_job_hash = hash_job_scoring_inputs(
                    build_full_description(
                        about_the_role=job.about_the_role,
                        key_responsibilities=job.key_responsibilities,
                        requirements=job.requirements,
                        preferred_certifications=job.preferred_certifications,
                        technical_competencies=job.technical_competencies,
                        what_we_offer=job.what_we_offer,
                        legacy_description=job.description,
                    ),
                    job.required_skills or [],
                    job.seniority_level,
                )
                assessment_is_current_for_job = (
                    current_job_hash == profile.ai_score_job_hash
                )

        if not assessment_is_current_for_job:
            response.ai_score = None
            response.ai_fit_summary = None
            response.ai_strengths = None
            response.ai_weaknesses = None
            response.ai_score_computed_at = None

        if profile.parsed_submission_id:
            submission = await self._ai_repo.get_submission_by_id(
                profile.parsed_submission_id
            )
            if submission and submission.r2_key:
                storage_service = get_storage_service()
                response.cv_download_url = await storage_service.generate_presigned_url(
                    submission.r2_key, expires_seconds=600
                )

        return response

    async def _check_sourced_cv_access(self, profile, current_user: User) -> None:
        """Raise unless the requester is entitled to view/modify this sourced profile.

        Shared by ``get_profile`` (read) and ``update_email`` (write) — the
        same access rule applies to viewing a sourced CV and mutating its
        contact details, so both must check it, not just the read path.
        Entitled: sourced it themselves, an admin, or holds an ACCEPTED
        introduction for this candidate (from any job).
        """
        from sqlalchemy import select

        from app.modules.introductions.enums import IntroductionStatus
        from app.modules.introductions.models import IntroductionRequest

        if profile.candidate_profile_id is not None:
            raise PermissionDeniedException(
                "Self-registered candidates are managed via /candidates/{id}, not this endpoint."
            )

        is_admin = current_user.role == UserRole.ADMIN.value
        is_owner = profile.added_by == current_user.id

        entitled = is_admin or is_owner
        if not entitled:
            accepted = await self._db.execute(
                select(IntroductionRequest.id)
                .where(
                    IntroductionRequest.employer_id == current_user.id,
                    IntroductionRequest.talent_pool_profile_id == profile.id,
                    IntroductionRequest.status == IntroductionStatus.ACCEPTED.value,
                )
                .limit(1)
            )
            entitled = accepted.scalar_one_or_none() is not None

        if not entitled:
            raise PermissionDeniedException(
                "You don't have access to this candidate's CV yet."
            )

    async def update_email(
        self,
        profile_id: uuid.UUID,
        email: str,
        current_user: User,
    ) -> TalentPoolProfileResponse:
        """Set an employer-entered override email for a candidate with no resolvable one.

        Used when the AI CV-parsing pipeline couldn't extract an email from
        a sourced CV, blocking the AI interview invite — see
        ``resolve_candidate_email`` in interviews/service.py for the
        priority this participates in.
        """
        profile = await self._repo.get_by_id(profile_id)
        if not profile:
            raise SubmissionNotFound()

        await self._check_sourced_cv_access(profile, current_user)

        profile = await self._repo.update(profile_id, {"override_email": email})
        await self._db.commit()
        return await self.get_profile(profile_id, current_user)

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
        is_admin: bool = False,
    ) -> "TalentMatchListResponse":
        """Return AI-matched talent pool profiles for a job, ranked by embedding similarity."""
        from app.core.storage import get_storage_service
        from app.modules.ai.scoring_service import hash_job_scoring_inputs
        from app.modules.applications.repository import ApplicationRepository
        from app.modules.jobs.schemas import build_full_description
        from app.modules.notifications.match_repository import (
            MatchNotificationRepository,
        )
        from app.modules.talent_pool.schema import (
            TalentMatchListResponse,
            TalentMatchResponse,
        )

        job_repo = JobRepository(self._db)
        application_repo = ApplicationRepository(self._db)
        storage_service = get_storage_service()

        job = await job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        # Admins can view matches for any job; employers only their own
        if job.employer_id != employer_id and not is_admin:
            raise PermissionDeniedException()

        if job.job_embedding is None:
            raise ValidationException(
                "Job embedding not yet generated — check back shortly."
            )

        # A profile's ai_score/ai_fit_summary/ai_strengths/ai_weaknesses are a
        # single set of columns computed against whichever job most recently
        # triggered scoring (see get_profile's docstring for the same
        # constraint) — not necessarily this job. Only surface them here if
        # they were actually computed against this job's current inputs,
        # same rule get_profile already enforces for the single-profile view.
        current_job_hash = hash_job_scoring_inputs(
            build_full_description(
                about_the_role=job.about_the_role,
                key_responsibilities=job.key_responsibilities,
                requirements=job.requirements,
                preferred_certifications=job.preferred_certifications,
                technical_competencies=job.technical_competencies,
                what_we_offer=job.what_we_offer,
                legacy_description=job.description,
            ),
            job.required_skills or [],
            job.seniority_level,
        )

        user_ids = await application_repo.get_user_ids_for_job(job_id)

        # Fetch which profiles are flagged as new before building the response
        match_notif_repo = MatchNotificationRepository(self._db)
        new_profile_ids = await match_notif_repo.get_new_profile_ids_for_job(job_id)

        # Use the shared helper — same scoring logic as the Celery task
        top_matches = await get_top_matches_for_job(
            self._db, job, employer_id, limit=limit, exclude_user_ids=user_ids
        )

        scored: list[dict] = []
        for profile, final_score, matched_skills in top_matches:
            fields = await resolve_match_display_fields(self._db, profile, employer_id)
            if profile.candidate_profile_id:
                ownership = "self_registered"
            elif profile.added_by == employer_id:
                ownership = "own_sourced"
            else:
                ownership = "admin_sourced"
            scored.append(
                {
                    "profile": profile,
                    "fields": fields,
                    "ownership": ownership,
                    "final_score": final_score,
                    "matched_skills": matched_skills,
                }
            )

        # Pass 2 — only for the final set that will actually display, resolve
        # the CV download URL (presigned URL generation + an extra query for
        # the admin_sourced/accepted-introduction check).
        items: list[TalentMatchResponse] = []
        for entry in scored:
            profile = entry["profile"]
            fields = entry["fields"]
            ownership = entry["ownership"]
            cv_download_url: str | None = None

            if ownership == "own_sourced":
                # Employer owns this CV — always provide the download URL
                if profile.parsed_submission and profile.parsed_submission.r2_key:
                    cv_download_url = await storage_service.generate_presigned_url(
                        profile.parsed_submission.r2_key,
                        expires_seconds=600,
                    )
            elif ownership == "admin_sourced":
                # Only unlock URL if an accepted introduction exists for this employer+profile
                from sqlalchemy import select

                from app.modules.introductions.enums import IntroductionStatus
                from app.modules.introductions.models import IntroductionRequest

                accepted = await self._db.execute(
                    select(IntroductionRequest.id)
                    .where(
                        IntroductionRequest.employer_id == employer_id,
                        IntroductionRequest.talent_pool_profile_id == profile.id,
                        IntroductionRequest.status == IntroductionStatus.ACCEPTED.value,
                    )
                    .limit(1)
                )
                if (
                    accepted.scalar_one_or_none()
                    and profile.parsed_submission
                    and profile.parsed_submission.r2_key
                ):
                    cv_download_url = await storage_service.generate_presigned_url(
                        profile.parsed_submission.r2_key,
                        expires_seconds=600,
                    )

            matched_skills = entry["matched_skills"]
            matched_lower = {s.lower() for s in matched_skills}
            remaining_skills = [
                s for s in fields["skills"] if s.lower() not in matched_lower
            ]

            items.append(
                TalentMatchResponse.from_match(
                    profile=profile,
                    similarity_score=entry["final_score"],
                    candidate_name=fields["name"],
                    current_title=fields["current_title"],
                    profession=fields["profession"],
                    years_of_experience=fields["years_of_experience"],
                    location=fields["location"],
                    top_skills=remaining_skills[:5],
                    matched_skills=matched_skills,
                    ownership=ownership,
                    cv_download_url=cv_download_url,
                    is_new=profile.id in new_profile_ids,
                    assessment_is_current_for_job=(
                        profile.ai_score_job_hash == current_job_hash
                    ),
                )
            )

        # Mark all new matches as viewed now that the employer has seen them
        await match_notif_repo.mark_job_matches_viewed(job_id)
        await self._db.commit()

        return TalentMatchListResponse(
            items=items,
            count=len(items),
            job_id=job_id,
        )

    async def score_profile_against_job(
        self,
        profile_id: uuid.UUID,
        job_id: uuid.UUID,
        current_user: User,
    ) -> dict:
        """
        Score a single profile against a given job.
        """
        from app.modules.ai.scoring_service import hash_job_scoring_inputs
        from app.modules.jobs.schemas import build_full_description

        profile = await self._repo.get_by_id(profile_id)
        if not profile:
            raise ProfileNotFoundException()

        job_repo = JobRepository(self._db)
        job = await job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        # Admins can trigger scoring for any job; employers only their own —
        # same rule get_job_matches already enforces for viewing matches.
        if job.employer_id != current_user.id and current_user.role != "ADMIN":
            raise PermissionDeniedException()

        current_job_hash = hash_job_scoring_inputs(
            build_full_description(
                about_the_role=job.about_the_role,
                key_responsibilities=job.key_responsibilities,
                requirements=job.requirements,
                preferred_certifications=job.preferred_certifications,
                technical_competencies=job.technical_competencies,
                what_we_offer=job.what_we_offer,
                legacy_description=job.description,
            ),
            job.required_skills or [],
            job.seniority_level,
        )

        if profile.ai_score_job_hash == current_job_hash:
            return {"status": "already_current"}

        try:
            score_talent_pool_profile_task.delay(
                str(profile.id),
                str(job.id),
            )
            return {"status": "queued"}
        except Exception as e:
            logger.error(f"Error scoring profile against job: {str(e)}")
            raise e
