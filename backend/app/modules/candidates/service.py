"""Business logic for candidate profiles, CVs, and documents."""

import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    CVErrorException,
    DocumentNotFoundError,
    PermissionDeniedException,
    ProfileNotFoundException,
    ValidationException,
)
from app.core.file_validation import (
    sanitize_filename,
    validate_document_upload,
    validate_pdf_upload,
)
from app.core.storage import StorageService
from app.modules.candidates.enums import AvailabilityBucket, VisibilityStatus
from app.modules.candidates.models import CandidateCvs
from app.modules.candidates.repository import CandidateRepository
from app.modules.candidates.schema import (
    CandidateCvsResponse,
    CandidateDocumentsResponse,
    CandidateSearchFilters,
    CandidateSearchProfile,
    CandidateSearchResponse,
    CandidateSearchResultItem,
    CertificationCreateSchema,
    CertificationResponse,
    EducationCreateSchema,
    EducationResponse,
    ProfileResponse,
    UpdateProfileSchema,
    WorkExperienceCreateSchema,
    WorkExperienceResponse,
)
from app.modules.jobs.enums import SeniorityLevel
from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME
from app.modules.users.enums import UserRole
from app.modules.users.models import User

# Seniority is not a stored column — it's derived from years_of_experience
# using the same SeniorityLevel enum jobs already use, so search filters and
# job postings speak the same vocabulary without a schema migration.
_SENIORITY_EXPERIENCE_RANGES: dict[SeniorityLevel, tuple[int, int | None]] = {
    SeniorityLevel.JUNIOR: (0, 2),
    SeniorityLevel.MID: (2, 5),
    SeniorityLevel.SENIOR: (5, 9),
    SeniorityLevel.LEAD: (9, 15),
    SeniorityLevel.EXECUTIVE: (15, None),
}

# Availability is likewise derived, from notice_period_days.
_AVAILABILITY_MAX_NOTICE_DAYS: dict[AvailabilityBucket, int | None] = {
    AvailabilityBucket.IMMEDIATE: 7,
    AvailabilityBucket.TWO_WEEKS: 14,
    AvailabilityBucket.ONE_MONTH: 30,
    AvailabilityBucket.FLEXIBLE: None,
}

logger = logging.getLogger(__name__)

_EXT_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


class CandidateService:
    """Orchestrates business logic for candidate profiles, CVs, and documents."""

    def __init__(self, db: AsyncSession, storage: StorageService, redis=None) -> None:
        """Initialise the service with a database session and storage backend.

        Args:
        ----
            db: The SQLAlchemy async session used for all DB operations.
            storage: The storage service used for file uploads and presigned URLs.

        """
        self._db = db
        self._storage = storage
        self._redis = redis
        self._repo = CandidateRepository(db)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def get_my_profile(self, user_id: uuid.UUID) -> ProfileResponse:
        """Return the profile for the currently authenticated candidate.

        Raises
        ------
            ProfileNotFoundException: If no profile exists for ``user_id``.

        """
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        return ProfileResponse.model_validate(profile)

    async def update_my_profile(
        self, user_id: uuid.UUID, data: UpdateProfileSchema
    ) -> ProfileResponse:
        """Apply a partial update to the authenticated candidate's profile.

        Commits the transaction and returns the updated profile.

        """
        profile = await self._repo.update(user_id, data)
        await self._db.commit()

        # Re-generate embedding if profile content changed
        from app.modules.ai.tasks import generate_candidate_embedding_task

        generate_candidate_embedding_task.delay(str(profile.id))

        return ProfileResponse.model_validate(profile)

    async def get_profile_by_id(
        self,
        profile_id: uuid.UUID,
        requesting_user,
        job_id: uuid.UUID | None = None,
    ) -> ProfileResponse:
        """Admin or Employer can view any candidate profile by profile ID.

        Enforces visibility rules for employer access:
        - PUBLIC: always accessible
        - APPLIED_ONLY: only if the candidate has applied to one of this employer's jobs
        - PRIVATE: never accessible to employers (raises PermissionDeniedException)
        """
        if requesting_user.role in (UserRole.ADMIN.value, UserRole.EMPLOYER.value):
            profile = await self._repo.get_by_id(profile_id)
            if profile is None:
                raise ProfileNotFoundException()

            if requesting_user.role == UserRole.EMPLOYER.value:
                # An accepted introduction grants access regardless of visibility setting
                from sqlalchemy import select

                from app.modules.introductions.enums import IntroductionStatus
                from app.modules.introductions.models import IntroductionRequest
                from app.modules.talent_pool.models import TalentPoolProfiles

                accepted_stmt = (
                    select(IntroductionRequest.id)
                    .join(
                        TalentPoolProfiles,
                        TalentPoolProfiles.id
                        == IntroductionRequest.talent_pool_profile_id,
                    )
                    .where(
                        IntroductionRequest.employer_id == requesting_user.id,
                        TalentPoolProfiles.candidate_profile_id == profile_id,
                        IntroductionRequest.status == IntroductionStatus.ACCEPTED.value,
                    )
                    .limit(1)
                )
                accepted = await self._db.execute(accepted_stmt)
                has_accepted_intro = accepted.scalar_one_or_none() is not None

                if not has_accepted_intro:
                    if profile.visibility == VisibilityStatus.PRIVATE.value:
                        raise PermissionDeniedException("This profile is private")

                    if profile.visibility == VisibilityStatus.APPLIED_ONLY.value:
                        has_application = (
                            await self._repo.candidate_has_applied_to_employer(
                                candidate_profile_id=profile.id,
                                employer_id=requesting_user.id,
                            )
                        )
                        if not has_application:
                            raise PermissionDeniedException(
                                "This candidate's profile is only visible to employers they have applied to"
                            )

                await self._repo.create_profile_viewed(
                    requesting_user.id, profile.id, job_id
                )
                await self._db.commit()

            return ProfileResponse.model_validate(profile)

        if requesting_user.role == UserRole.CANDIDATE.value:
            profile = await self._repo.get_by_user_id(requesting_user.id)
            if profile is None or profile.id != profile_id:
                raise ProfileNotFoundException()
            return ProfileResponse.model_validate(profile)

        raise ProfileNotFoundException()

    async def list_all_profiles(self) -> list[ProfileResponse]:
        """Return all candidate profiles (admin use only)."""
        profiles = await self._repo.list_all()
        return [ProfileResponse.model_validate(p) for p in profiles]

    async def search_candidates(
        self, filters: CandidateSearchFilters, current_user: User
    ) -> CandidateSearchResponse:
        """Employer-facing structured search over the talent pool.

        Queries ``TalentPoolProfiles`` — the same table and the same
        visibility/ownership rule ``talent_pool`` uses for job-to-candidate
        matching (see ``find_matches_for_job`` /
        ``TalentPoolRepository.find_candidates_for_search``), entered from a
        free-text/filter search instead of a job. This covers BOTH
        self-registered candidates (with a linked CandidateProfile) and
        employer-sourced CVs (no login, no CandidateProfile row) — searching
        CandidateProfile alone would have silently excluded every sourced
        candidate. If ``filters.query`` is set, it's embedded and results are
        ranked by pgvector cosine distance; otherwise filters/scoring run in
        Python over resolved display fields, mirroring
        ``get_top_matches_for_job``'s overfetch-then-filter pattern (skills
        and current title live in different places for sourced vs
        self-registered profiles, so there's no single SQL predicate for
        them). Every result carries a human-readable ``explanation`` so
        ranking is never a black box.

        The whole endpoint — structured filters included, not just the
        semantic ``query`` field — is Professional+. Candidate Search is
        marketed as a paid-tier feature on the pricing page; Starter gets
        no access to it at all.
        """
        from app.modules.talent_pool.repository import TalentPoolRepository
        from app.modules.talent_pool.service import resolve_match_display_fields

        if current_user.role != "ADMIN":
            from app.modules.billing.service import BillingService

            billing_service = BillingService(self._db)
            await billing_service.assert_professional_or_above(
                current_user.organization_id
            )

        min_experience = filters.min_experience
        max_experience = filters.max_experience
        if filters.seniority:
            # Intersect the requested seniority bands with any explicit
            # experience range the recruiter also set.
            band_min = min(
                _SENIORITY_EXPERIENCE_RANGES[s][0] for s in filters.seniority
            )
            band_maxes = [_SENIORITY_EXPERIENCE_RANGES[s][1] for s in filters.seniority]
            band_max = None if any(m is None for m in band_maxes) else max(band_maxes)
            min_experience = (
                band_min if min_experience is None else max(min_experience, band_min)
            )
            if band_max is not None:
                max_experience = (
                    band_max
                    if max_experience is None
                    else min(max_experience, band_max)
                )

        max_notice_period_days = None
        if filters.availability:
            notice_caps = [
                _AVAILABILITY_MAX_NOTICE_DAYS[a] for a in filters.availability
            ]
            if not any(cap is None for cap in notice_caps):
                max_notice_period_days = max(notice_caps)
            # If FLEXIBLE is among the requested buckets, no cap is applied —
            # FLEXIBLE means "any availability is fine".

        query_embedding = None
        if filters.query:
            from app.modules.ai.service import get_ai_service

            ai_service = get_ai_service()
            query_embedding = await ai_service.generate_embedding(filters.query)

        talent_pool_repo = TalentPoolRepository(self._db)
        # Overfetch — filtering happens in Python after resolving display
        # fields, same reason get_top_matches_for_job overfetches: a
        # skill/title match can promote a profile that wasn't in the top-N
        # by raw embedding distance (or wasn't ranked at all, filter-only).
        fetch_limit = min(50 * 4, 200)
        rows = await talent_pool_repo.find_candidates_for_search(
            employer_id=current_user.id,
            query_embedding=query_embedding,
            limit=fetch_limit,
        )

        results = []
        for profile, distance in rows:
            fields = await resolve_match_display_fields(
                self._db, profile, current_user.id
            )

            # Current title, for self-registered candidates without a parsed
            # CV: fall back to their most recent work experience entry.
            current_title = fields["current_title"]
            if not current_title and profile.candidate_profile:
                current = next(
                    (
                        we
                        for we in (profile.candidate_profile.work_experiences or [])
                        if we.is_current
                    ),
                    None,
                )
                if current:
                    current_title = current.job_title

            notice_period_days = (
                profile.candidate_profile.notice_period_days
                if profile.candidate_profile
                else None
            )

            if profile.candidate_profile_id:
                ownership = "self_registered"
            elif profile.added_by == current_user.id:
                ownership = "own_sourced"
            else:
                ownership = "admin_sourced"

            # self_registered's CV/profile access is governed by the
            # candidate's own visibility setting (CandidateProfilePanel's
            # endpoint already enforces this); own_sourced already has full
            # access to their own upload. Only admin_sourced needs a real
            # check — an employer only has access once a candidate has
            # accepted an introduction to them, from any job.
            if ownership == "admin_sourced":
                from app.modules.introductions.repository import (
                    IntroductionRepository,
                )

                has_cv_access = await IntroductionRepository(
                    self._db
                ).has_accepted_introduction(
                    employer_id=current_user.id, talent_pool_profile_id=profile.id
                )
            else:
                has_cv_access = True

            result = self._to_search_result(
                profile=profile,
                distance=distance,
                fields=fields,
                current_title=current_title,
                notice_period_days=notice_period_days,
                ownership=ownership,
                has_cv_access=has_cv_access,
                filters=filters,
                min_experience=min_experience,
                max_experience=max_experience,
                max_notice_period_days=max_notice_period_days,
            )
            if result is not None:
                results.append(result)

        results.sort(key=lambda r: r.match_score, reverse=True)
        results = results[:50]

        return CandidateSearchResponse(
            results=results, total=len(results), filters_applied=filters
        )

    @staticmethod
    def _to_search_result(
        *,
        profile,
        distance: float | None,
        fields: dict,
        current_title: str | None,
        notice_period_days: int | None,
        ownership: str,
        has_cv_access: bool,
        filters: CandidateSearchFilters,
        min_experience: int | None,
        max_experience: int | None,
        max_notice_period_days: int | None,
    ) -> CandidateSearchResultItem | None:
        """Apply remaining (non-SQL) filters and build one ranked, explainable result.

        Returns ``None`` if the profile doesn't actually satisfy the
        filters — skills/experience/location/availability are checked here
        rather than in SQL because sourced profiles resolve them from
        parsed-CV JSON, not columns (see ``resolve_match_display_fields``).
        """
        explanation: list[str] = []
        matched_skills: list[str] = []

        years = fields["years_of_experience"]
        if min_experience is not None and (years is None or years < min_experience):
            return None
        if max_experience is not None and (years is None or years > max_experience):
            return None

        if filters.location:
            if (
                not fields["location"]
                or filters.location.lower() not in fields["location"].lower()
            ):
                return None

        if max_notice_period_days is not None:
            # Unknown notice period can't satisfy a specific availability ask.
            if (
                notice_period_days is None
                or notice_period_days > max_notice_period_days
            ):
                return None

        semantic_score = None
        if distance is not None:
            semantic_score = max(0.0, (1 - distance) * 100)
            explanation.append(
                f"Semantic match to your search query ({semantic_score:.0f}% similarity)"
            )

        skill_score = None
        if filters.skills:
            profile_skills = {s.lower() for s in (fields["skills"] or [])}
            requested = {s.lower() for s in filters.skills}
            matched = profile_skills & requested
            matched_skills = [
                s for s in (fields["skills"] or []) if s.lower() in matched
            ]
            skill_score = (len(matched) / len(requested)) * 100 if requested else 0.0
            if matched:
                explanation.append(
                    f"Matches {len(matched)} of {len(requested)} requested skills: "
                    + ", ".join(matched_skills)
                )
            else:
                return None  # skills were requested and none matched — not a result

        title_score = None
        if filters.job_title:
            # Token-based, ILIKE-style partial match rather than a whole-phrase
            # substring: with the talent pool still small, requiring the full
            # query ("python developer") to appear verbatim in a title would
            # miss "Python Engineer" or "Senior Python Developer" entirely.
            # Matching on any token instead trades some precision for recall,
            # which is the right side to err on until there's enough volume
            # for exact-phrase matching to reliably return anything.
            haystack = f"{current_title or ''} {fields.get('profession') or ''}".lower()
            query_tokens = {
                t for t in re.split(r"[^a-z0-9]+", filters.job_title.lower()) if t
            }
            matched_tokens = {t for t in query_tokens if t in haystack}
            if matched_tokens:
                title_score = (
                    (len(matched_tokens) / len(query_tokens)) * 100
                    if query_tokens
                    else 0.0
                )
                explanation.append(
                    f"Title ({current_title or fields.get('profession') or 'unknown'}) "
                    f"matches \"{'/'.join(sorted(matched_tokens))}\" from your job title search"
                )
            else:
                return None  # job title requested and no token matched — not a result

        if min_experience is not None or max_experience is not None:
            explanation.append(
                f"{years if years is not None else 'Unknown'} years of experience"
            )

        if filters.location and fields["location"]:
            explanation.append(f"Located in {fields['location']}")

        if filters.availability:
            explanation.append(
                f"Notice period: {notice_period_days} days"
                if notice_period_days is not None
                else "Notice period not specified"
            )

        # Blend whatever scoring signals are available; fall back to a flat
        # baseline so filter-only searches (no skills/query/title) still
        # rank results instead of returning an arbitrary DB order.
        signals = [
            s for s in (semantic_score, skill_score, title_score) if s is not None
        ]
        match_score = sum(signals) / len(signals) if signals else 60.0

        return CandidateSearchResultItem(
            profile=CandidateSearchProfile(
                id=profile.id,
                candidate_profile_id=profile.candidate_profile_id,
                ownership=ownership,
                has_cv_access=has_cv_access,
                candidate_name=fields["name"],
                current_title=current_title,
                profession=fields.get("profession"),
                years_of_experience=years,
                notice_period_days=notice_period_days,
                location=fields["location"],
                skills=fields["skills"] or [],
                summary=fields.get("summary"),
            ),
            match_score=round(match_score, 1),
            matched_skills=matched_skills,
            explanation=explanation,
        )

    async def get_profile_views(
        self, user_id: uuid.UUID, cursor: str | None = None, limit: int = 20
    ):
        """Return paginated profile view records for the authenticated candidate."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        paginated = await self._repo.get_profile_views(profile.id, cursor, limit)

        items = []
        for view in paginated["items"]:
            employer = getattr(view, "employer", None)
            employer_profile = getattr(employer, "organization", None)
            if employer_profile and employer_profile.company_name:
                company_name = employer_profile.company_name
            elif employer and employer.role == "ADMIN":
                company_name = PLATFORM_COMPANY_NAME
            else:
                company_name = None
            items.append(
                {
                    "id": view.id,
                    "viewed_at": view.viewed_at,
                    "company_name": company_name,
                    "company_logo_url": (
                        employer_profile.company_logo_url if employer_profile else None
                    ),
                    "job_title": None,  # TODO: load job title when job_id is set
                }
            )

        return {"items": items, "next_cursor": paginated.get("next_cursor")}

    # ------------------------------------------------------------------
    # CVs
    # ------------------------------------------------------------------

    async def get_cv(self, cv_id):
        """Return a CV by its primary key, or None if not found."""
        return self._db.get(CandidateCvs, cv_id)

    async def upload_cv(
        self, user_id: uuid.UUID, file: bytes, filename: str
    ) -> CandidateCvsResponse:
        """Validate, upload, and persist a candidate CV.

        The first CV uploaded is automatically set as the default.
        Raises ``ValidationException`` if the candidate already has 5 CVs.

        Args:
        ----
            user_id: UUID of the authenticated candidate.
            file: Raw file bytes.
            filename: Original filename from the upload.

        Returns:
        -------
            The newly created :class:`CandidateCvsResponse`.

        Raises:
        ------
            ProfileNotFoundException: If the candidate has no profile.
            ValidationException: If the CV limit (5) has been reached.
            CVErrorException: If the storage upload fails.

        """
        from app.core.cv_pipeline.layer1_extraction import extract_text_from_pdf

        validate_pdf_upload(file, filename)

        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        # Count query on cvs available
        cv_count = await self._repo.count_cvs(profile.id)
        if cv_count >= 5:
            raise ValidationException(message="Maximum of 5 CVs allowed per candidate")

        is_first = not await self._repo.has_any_cv(profile.id)
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        key = f"cvs/{user_id}/{timestamp}_{sanitize_filename(filename)}"

        try:
            uploaded_key = await self._storage.upload_file(file, key, "application/pdf")
        except Exception as e:
            logger.error(f"R2 upload failed for user {user_id}: {e}")
            raise CVErrorException(str(e)) from e

        cv = await self._repo.save_cv(
            profile.id, uploaded_key, filename, is_default=is_first
        )

        # Trigger CV parsing pipeline — create a ParsedCVSubmission row for tracking
        try:
            import hashlib
            import hmac as hmac_module
            import json

            from app.core.config import settings
            from app.core.cv_pipeline.layer1_extraction import extract_text_from_pdf
            from app.modules.ai.enums import CVParsingStatus
            from app.modules.ai.models import ParsedCVSubmission

            text_result = extract_text_from_pdf(file)
            cv_text_hash = hmac_module.new(
                settings.hmac_secret.encode(),
                (text_result.text or "").encode(),
                hashlib.sha256,
            ).hexdigest()
            cache_key = f"cv_parse:{cv_text_hash}"

            # Check Redis cache
            cached = None
            if self._redis:
                try:
                    cached = await self._redis.get(cache_key)
                except Exception:
                    pass

            if cached:
                logger.info("CV ALREADY PARSED IN REDIS")
                parsed_data = json.loads(cached)
                submission = ParsedCVSubmission(
                    uploaded_by=user_id,
                    filename=filename,
                    r2_key=uploaded_key,
                    cv_text_hash=cv_text_hash,
                    parse_status=CVParsingStatus.COMPLETED.value,
                    parsed_data=parsed_data,
                )
                self._db.add(submission)
                await self._db.flush()
                cv.cv_parse_status = CVParsingStatus.COMPLETED.value
                cv.submission_id = submission.id
            else:
                submission = ParsedCVSubmission(
                    uploaded_by=user_id,
                    filename=filename,
                    r2_key=uploaded_key,
                    cv_text_hash=cv_text_hash,
                    parse_status=CVParsingStatus.PENDING.value,
                )
                self._db.add(submission)
                await self._db.flush()
                cv.submission_id = submission.id

                from app.modules.ai.tasks import run_full_pipeline_task

                run_full_pipeline_task.delay(
                    submission_id=str(submission.id),
                    cache_key=cache_key,
                    file=file,
                )

        except Exception as e:
            logger.error(f"CV parsing trigger failed for user {user_id}: {e}")
            # Don't fail the upload — parsing is best-effort

        # Recompute profile completion — a CV is required for is_profile_complete=True.
        # Expire the cached profile so the reload picks up the newly inserted CV row.
        from app.modules.candidates.repository import compute_profile_completion

        await self._db.refresh(profile, ["cvs"])
        profile.is_profile_complete = compute_profile_completion(profile)
        await self._db.flush()

        await self._db.commit()

        # Fire after commit, not before — a Celery worker on a separate DB
        # connection can't see this transaction's changes until it's committed.
        if profile.is_profile_complete:
            from app.modules.ai.tasks import generate_candidate_embedding_task

            generate_candidate_embedding_task.delay(str(profile.id))

        return CandidateCvsResponse.model_validate(cv)

    async def delete_cv(self, cv_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a CV from storage and the database.

        Promotes the next most-recent CV to default if the deleted one was the default.

        Raises
        ------
            ProfileNotFoundException: If the candidate has no profile.
            DocumentNotFoundError: If the CV does not exist.
            PermissionDeniedException: If the CV belongs to a different candidate.

        """
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        cv = await self._repo.get_cv(cv_id)
        if cv is None:
            raise DocumentNotFoundError()
        if cv.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to delete this CV"
            )

        was_default = cv.is_default
        await self._storage.delete_file(cv.key)
        await self._repo.delete_cv(cv)

        if was_default:
            await self._repo.promote_next_default_cv(profile.id)

        await self._db.commit()

    async def set_cv_default(self, cv_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Mark a CV as the candidate's default, clearing the flag on all others.

        Raises
        ------
            ProfileNotFoundException: If the candidate has no profile.
            DocumentNotFoundError: If the CV does not exist.
            PermissionDeniedException: If the CV belongs to a different candidate.

        """
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        cv = await self._repo.get_cv(cv_id)
        if cv is None:
            raise DocumentNotFoundError()
        if cv.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to set this CV as default"
            )

        await self._repo.set_default_cv(profile.id, cv_id)
        await self._db.commit()

    async def get_cvs(self, user_id: uuid.UUID) -> list[CandidateCvsResponse]:
        """Return all CVs for the authenticated candidate."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        cvs = await self._repo.get_all_cvs(profile.id)
        return [CandidateCvsResponse.model_validate(cv) for cv in cvs]

    async def generate_cv_url(self, cv_id: uuid.UUID, user_id: uuid.UUID) -> str:
        """Generate a 15-minute presigned URL. Enforces ownership."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        cv = await self._repo.get_cv(cv_id)
        if cv is None:
            raise DocumentNotFoundError()
        if cv.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to access this CV"
            )

        return await self._storage.generate_presigned_url(cv.key, 60 * 15)

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def upload_document(
        self, user_id: uuid.UUID, file: bytes, filename: str
    ) -> CandidateDocumentsResponse:
        """Validate, upload, and persist a supporting document.

        Args:
        ----
            user_id: UUID of the authenticated candidate.
            file: Raw file bytes.
            filename: Original filename from the upload.

        Returns:
        -------
            The newly created :class:`CandidateDocumentsResponse`.

        Raises:
        ------
            ProfileNotFoundException: If the candidate has no profile.
            CVErrorException: If the storage upload fails.

        """
        validate_document_upload(file, filename)

        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        ext = filename.rsplit(".", 1)[-1].lower()
        content_type = _EXT_TO_MIME.get(ext, "application/octet-stream")
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        key = f"documents/{user_id}/{timestamp}_{sanitize_filename(filename)}"

        try:
            uploaded_key = await self._storage.upload_file(file, key, content_type)
        except Exception as e:
            logger.error(f"Document upload failed for user {user_id}: {e}")
            raise CVErrorException(str(e)) from e

        doc = await self._repo.save_document(profile.id, uploaded_key, filename, ext)
        await self._db.commit()
        return CandidateDocumentsResponse.model_validate(doc)

    async def delete_document(self, document_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a supporting document from storage and the database.

        Raises
        ------
            ProfileNotFoundException: If the candidate has no profile.
            DocumentNotFoundError: If the document does not exist.
            PermissionDeniedException: If the document belongs to a different candidate.

        """
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        document = await self._repo.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError()
        if document.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to delete this document"
            )

        await self._storage.delete_file(document.key)
        await self._repo.delete_document(document)
        await self._db.commit()

    async def get_my_documents(
        self, user_id: uuid.UUID
    ) -> list[CandidateDocumentsResponse]:
        """Return all supporting documents for the authenticated candidate."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        docs = await self._repo.get_all_documents(profile.id)
        return [CandidateDocumentsResponse.model_validate(d) for d in docs]

    async def generate_document_url(
        self, document_id: uuid.UUID, user_id: uuid.UUID
    ) -> str:
        """Generate a 15-minute presigned URL for a supporting document. Enforces ownership."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        document = await self._repo.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError()
        if document.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to access this document"
            )

        return await self._storage.generate_presigned_url(document.key, 60 * 15)

    # ------------------------------------------------------------------
    # Work Experience
    # ------------------------------------------------------------------

    async def add_work_experience(
        self, user_id: uuid.UUID, data: WorkExperienceCreateSchema
    ) -> WorkExperienceResponse:
        """Add a work experience entry to the candidate's profile."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.add_work_experience(profile.id, data)
        await self._db.commit()
        return WorkExperienceResponse.model_validate(entry)

    async def delete_work_experience(
        self, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a work experience entry, enforcing profile ownership."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.get_work_experience(entry_id)
        if entry is None:
            raise DocumentNotFoundError()
        if entry.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to delete this entry"
            )
        await self._repo.delete_work_experience(entry)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Education
    # ------------------------------------------------------------------

    async def add_education(
        self, user_id: uuid.UUID, data: EducationCreateSchema
    ) -> EducationResponse:
        """Add an education entry to the candidate's profile."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.add_education(profile.id, data)
        await self._db.commit()
        return EducationResponse.model_validate(entry)

    async def delete_education(self, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete an education entry, enforcing profile ownership."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.get_education(entry_id)
        if entry is None:
            raise DocumentNotFoundError()
        if entry.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to delete this entry"
            )
        await self._repo.delete_education(entry)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    async def add_certification(
        self, user_id: uuid.UUID, data: CertificationCreateSchema
    ) -> CertificationResponse:
        """Add a certification entry to the candidate's profile."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.add_certification(profile.id, data)
        await self._db.commit()
        return CertificationResponse.model_validate(entry)

    async def delete_certification(
        self, entry_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        """Delete a certification entry, enforcing profile ownership."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.get_certification(entry_id)
        if entry is None:
            raise DocumentNotFoundError()
        if entry.candidate_id != profile.id:
            raise PermissionDeniedException(
                "You do not have permission to delete this entry"
            )
        await self._repo.delete_certification(entry)
        await self._db.commit()
