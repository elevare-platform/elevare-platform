"""Business logic for candidate profiles, CVs, and documents."""

import logging
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
from app.modules.candidates.enums import VisibilityStatus
from app.modules.candidates.models import CandidateCvs
from app.modules.candidates.repository import CandidateRepository
from app.modules.candidates.schema import (
    CandidateCvsResponse,
    CandidateDocumentsResponse,
    CertificationCreateSchema,
    CertificationResponse,
    EducationCreateSchema,
    EducationResponse,
    ProfileResponse,
    UpdateProfileSchema,
    WorkExperienceCreateSchema,
    WorkExperienceResponse,
)
from app.modules.users.enums import UserRole

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
            employer_profile = getattr(
                getattr(view, "employer", None), "employer_profile", None
            )
            items.append(
                {
                    "id": view.id,
                    "viewed_at": view.viewed_at,
                    "company_name": (
                        employer_profile.company_name if employer_profile else None
                    ),
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
