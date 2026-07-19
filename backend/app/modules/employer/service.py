"""Business logic for employer-specific operations."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentNotFoundError,
    KYCAlreadySubmittedException,
    PermissionDeniedException,
    ProfileNotFoundException,
    ValidationException,
)
from app.core.file_validation import sanitize_filename, validate_document_upload
from app.core.storage import StorageService
from app.modules.employer.enums import KYCStatus
from app.modules.employer.repository import EmployerRepository
from app.modules.employer.schemas import (
    EmployerStats,
    KYCDocumentResponse,
    KYCStatusResponse,
)

logger = logging.getLogger(__name__)

_EXT_TO_MIME: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}

KYC_DOCUMENT_TYPES = {"Business Registration", "Tax ID", "Proof of Address"}


class EmployerService:
    """Business logic for employer-specific operations."""

    def __init__(self, db: AsyncSession, storage: StorageService | None = None):
        """Initialise the service with an async database session."""
        self._db = db
        self._repo = EmployerRepository(db)
        self._storage = storage

    async def get_employer_stats(self, employer_id: uuid.UUID) -> EmployerStats:
        """Return job statistics scoped to the given employer."""
        return await self._repo.get_stats(employer_id)

    # ------------------------------------------------------------------
    # KYC
    # ------------------------------------------------------------------

    async def get_kyc_status(self, user_id: uuid.UUID) -> KYCStatusResponse:
        """Return the KYC status and documents for the authenticated employer."""
        profile = await self._repo.get_employer_profile_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()
        return KYCStatusResponse(
            kyc_status=profile.kyc_status or KYCStatus.NOT_SUBMITTED.value,
            kyc_rejection_reason=profile.kyc_rejection_reason,
            kyc_submitted_at=profile.kyc_submitted_at,
            kyc_reviewed_at=profile.kyc_reviewed_at,
            documents=[KYCDocumentResponse.model_validate(d) for d in profile.kyc_documents],
        )

    async def upload_kyc_document(
        self,
        user_id: uuid.UUID,
        file: bytes,
        filename: str,
        document_type: str,
    ) -> KYCDocumentResponse:
        """Validate, upload, and persist a KYC document.

        Only allowed when kyc_status is NOT_SUBMITTED or REJECTED.
        """
        if document_type not in KYC_DOCUMENT_TYPES:
            raise ValidationException(
                message=f"document_type must be one of: {', '.join(sorted(KYC_DOCUMENT_TYPES))}"
            )

        validate_document_upload(file, filename)

        profile = await self._repo.get_employer_profile_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        current_status = profile.kyc_status or KYCStatus.NOT_SUBMITTED.value
        if current_status == KYCStatus.PENDING.value:
            raise KYCAlreadySubmittedException(
                message="Cannot upload documents while KYC is under review"
            )
        if current_status == KYCStatus.APPROVED.value:
            raise KYCAlreadySubmittedException(
                message="KYC is already approved"
            )

        ext = filename.rsplit(".", 1)[-1].lower()
        content_type = _EXT_TO_MIME.get(ext, "application/octet-stream")
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        key = f"kyc/{profile.id}/{timestamp}_{sanitize_filename(filename)}"

        try:
            uploaded_key = await self._storage.upload_file(file, key, content_type)
        except Exception as e:
            logger.error("KYC document upload failed for user %s: %s", user_id, e)
            raise ValidationException(message="File upload failed. Please try again.") from e

        doc = await self._repo.save_kyc_document(
            employer_profile_id=profile.id,
            key=uploaded_key,
            filename=filename,
            document_type=document_type,
        )
        await self._db.commit()
        return KYCDocumentResponse.model_validate(doc)

    async def delete_kyc_document(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> None:
        """Delete a KYC document. Only allowed when status is NOT_SUBMITTED or REJECTED."""
        profile = await self._repo.get_employer_profile_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        current_status = profile.kyc_status or KYCStatus.NOT_SUBMITTED.value
        if current_status in (KYCStatus.PENDING.value, KYCStatus.APPROVED.value):
            raise PermissionDeniedException(
                message="Cannot delete documents while KYC is pending or approved"
            )

        doc = await self._repo.get_kyc_document(document_id)
        if doc is None:
            raise DocumentNotFoundError()
        if doc.employer_profile_id != profile.id:
            raise PermissionDeniedException()

        await self._storage.delete_file(doc.key)
        await self._repo.delete_kyc_document(doc)
        await self._db.commit()

    async def generate_kyc_document_url(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> str:
        """Generate a 15-minute presigned URL for a KYC document."""
        profile = await self._repo.get_employer_profile_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        doc = await self._repo.get_kyc_document(document_id)
        if doc is None:
            raise DocumentNotFoundError()
        if doc.employer_profile_id != profile.id:
            raise PermissionDeniedException()

        return await self._storage.generate_presigned_url(doc.key, 60 * 15)

    async def submit_kyc(self, user_id: uuid.UUID) -> KYCStatusResponse:
        """Flip kyc_status to PENDING. Requires at least one document uploaded."""
        profile = await self._repo.get_employer_profile_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        current_status = profile.kyc_status or KYCStatus.NOT_SUBMITTED.value
        if current_status == KYCStatus.PENDING.value:
            raise KYCAlreadySubmittedException()
        if current_status == KYCStatus.APPROVED.value:
            raise KYCAlreadySubmittedException(message="KYC is already approved")

        if not profile.kyc_documents:
            raise ValidationException(
                message="Upload at least one document before submitting for verification"
            )

        await self._repo.set_kyc_status(profile, KYCStatus.PENDING.value)
        await self._db.commit()

        return KYCStatusResponse(
            kyc_status=profile.kyc_status,
            kyc_rejection_reason=profile.kyc_rejection_reason,
            kyc_submitted_at=profile.kyc_submitted_at,
            kyc_reviewed_at=profile.kyc_reviewed_at,
            documents=[KYCDocumentResponse.model_validate(d) for d in profile.kyc_documents],
        )
