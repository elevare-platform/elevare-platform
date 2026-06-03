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

    def __init__(self, db: AsyncSession, storage: StorageService) -> None:
        """Initialise the service with a database session and storage backend.

        Args:
            db: The SQLAlchemy async session used for all DB operations.
            storage: The storage service used for file uploads and presigned URLs.

        """
        self._db = db
        self._storage = storage
        self._repo = CandidateRepository(db)

    # ------------------------------------------------------------------
    # Profile
    # ------------------------------------------------------------------

    async def get_my_profile(self, user_id: uuid.UUID) -> ProfileResponse:
        """Return the profile for the currently authenticated candidate.

        Raises:
            ProfileNotFoundException: If no profile exists for ``user_id``.

        """
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        return ProfileResponse.model_validate(profile)

    async def update_my_profile(self, user_id: uuid.UUID, data: UpdateProfileSchema) -> ProfileResponse:
        """Apply a partial update to the authenticated candidate's profile.

        Commits the transaction and returns the updated profile.

        """
        profile = await self._repo.update(user_id, data)
        await self._db.commit()
        return ProfileResponse.model_validate(profile)

    async def get_profile_by_id(self, profile_id: uuid.UUID, requesting_user) -> ProfileResponse:
        """Admin or Employer can view any candidate profile by profile ID."""
        if requesting_user.role in (UserRole.ADMIN.value, UserRole.EMPLOYER.value):
            profile = await self._repo.get_by_id(profile_id)
            if profile is None:
                raise ProfileNotFoundException()
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

    # ------------------------------------------------------------------
    # CVs
    # ------------------------------------------------------------------

    async def get_cv(self, cv_id):
        return self._db.get(CandidateCvs, cv_id)

    async def upload_cv(self, user_id: uuid.UUID, file: bytes, filename: str) -> CandidateCvsResponse:
        """Validate, upload, and persist a candidate CV.

        The first CV uploaded is automatically set as the default.
        Raises ``ValidationException`` if the candidate already has 5 CVs.

        Args:
            user_id: UUID of the authenticated candidate.
            file: Raw file bytes.
            filename: Original filename from the upload.

        Returns:
            The newly created :class:`CandidateCvsResponse`.

        Raises:
            ProfileNotFoundException: If the candidate has no profile.
            ValidationException: If the CV limit (5) has been reached.
            CVErrorException: If the storage upload fails.

        """
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

        cv = await self._repo.save_cv(profile.id, uploaded_key, filename, is_default=is_first)
        await self._db.commit()
        return CandidateCvsResponse.model_validate(cv)

    async def delete_cv(self, cv_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete a CV from storage and the database.

        Promotes the next most-recent CV to default if the deleted one was the default.

        Raises:
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
            raise PermissionDeniedException("You do not have permission to delete this CV")

        was_default = cv.is_default
        await self._storage.delete_file(cv.key)
        await self._repo.delete_cv(cv)

        if was_default:
            await self._repo.promote_next_default_cv(profile.id)

        await self._db.commit()

    async def set_cv_default(self, cv_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Mark a CV as the candidate's default, clearing the flag on all others.

        Raises:
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
            raise PermissionDeniedException("You do not have permission to set this CV as default")

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
            raise PermissionDeniedException("You do not have permission to access this CV")

        return await self._storage.generate_presigned_url(cv.key, 60 * 15)

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def upload_document(self, user_id: uuid.UUID, file: bytes, filename: str) -> CandidateDocumentsResponse:
        """Validate, upload, and persist a supporting document.

        Args:
            user_id: UUID of the authenticated candidate.
            file: Raw file bytes.
            filename: Original filename from the upload.

        Returns:
            The newly created :class:`CandidateDocumentsResponse`.

        Raises:
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

        Raises:
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
            raise PermissionDeniedException("You do not have permission to delete this document")

        await self._storage.delete_file(document.key)
        await self._repo.delete_document(document)
        await self._db.commit()

    async def get_my_documents(self, user_id: uuid.UUID) -> list[CandidateDocumentsResponse]:
        """Return all supporting documents for the authenticated candidate."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        docs = await self._repo.get_all_documents(profile.id)
        return [CandidateDocumentsResponse.model_validate(d) for d in docs]

    async def generate_document_url(self, document_id: uuid.UUID, user_id: uuid.UUID) -> str:
        """Generate a 15-minute presigned URL for a supporting document. Enforces ownership."""
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        document = await self._repo.get_document(document_id)
        if document is None:
            raise DocumentNotFoundError()
        if document.candidate_id != profile.id:
            raise PermissionDeniedException("You do not have permission to access this document")

        return await self._storage.generate_presigned_url(document.key, 60 * 15)

    # ------------------------------------------------------------------
    # Work Experience
    # ------------------------------------------------------------------

    async def add_work_experience(
        self, user_id: uuid.UUID, data: WorkExperienceCreateSchema
    ) -> WorkExperienceResponse:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.add_work_experience(profile.id, data)
        await self._db.commit()
        return WorkExperienceResponse.model_validate(entry)

    async def delete_work_experience(self, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.get_work_experience(entry_id)
        if entry is None:
            raise DocumentNotFoundError()
        if entry.candidate_id != profile.id:
            raise PermissionDeniedException("You do not have permission to delete this entry")
        await self._repo.delete_work_experience(entry)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Education
    # ------------------------------------------------------------------

    async def add_education(
        self, user_id: uuid.UUID, data: EducationCreateSchema
    ) -> EducationResponse:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.add_education(profile.id, data)
        await self._db.commit()
        return EducationResponse.model_validate(entry)

    async def delete_education(self, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.get_education(entry_id)
        if entry is None:
            raise DocumentNotFoundError()
        if entry.candidate_id != profile.id:
            raise PermissionDeniedException("You do not have permission to delete this entry")
        await self._repo.delete_education(entry)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    async def add_certification(
        self, user_id: uuid.UUID, data: CertificationCreateSchema
    ) -> CertificationResponse:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.add_certification(profile.id, data)
        await self._db.commit()
        return CertificationResponse.model_validate(entry)

    async def delete_certification(self, entry_id: uuid.UUID, user_id: uuid.UUID) -> None:
        profile = await self._repo.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        entry = await self._repo.get_certification(entry_id)
        if entry is None:
            raise DocumentNotFoundError()
        if entry.candidate_id != profile.id:
            raise PermissionDeniedException("You do not have permission to delete this entry")
        await self._repo.delete_certification(entry)
        await self._db.commit()
