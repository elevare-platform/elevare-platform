"""Business logic for employer-specific operations."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DocumentNotFoundError,
    KYCAlreadySubmittedException,
    NotFoundException,
    PermissionDeniedException,
    ProfileNotFoundException,
    ValidationException,
)
from app.core.file_validation import sanitize_filename, validate_document_upload
from app.core.storage import StorageService
from app.modules.employer.enums import KYCStatus, OrganizationRole
from app.modules.employer.repository import EmployerRepository
from app.modules.employer.schemas import (
    EmployerStats,
    KYCDocumentResponse,
    KYCStatusResponse,
    TeamMemberResponse,
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
        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()
        return KYCStatusResponse(
            kyc_status=organization.kyc_status or KYCStatus.NOT_SUBMITTED.value,
            kyc_rejection_reason=organization.kyc_rejection_reason,
            kyc_submitted_at=organization.kyc_submitted_at,
            kyc_reviewed_at=organization.kyc_reviewed_at,
            documents=[
                KYCDocumentResponse.model_validate(d)
                for d in organization.kyc_documents
            ],
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

        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()

        current_status = organization.kyc_status or KYCStatus.NOT_SUBMITTED.value
        if current_status == KYCStatus.PENDING.value:
            raise KYCAlreadySubmittedException(
                message="Cannot upload documents while KYC is under review"
            )
        if current_status == KYCStatus.APPROVED.value:
            raise KYCAlreadySubmittedException(message="KYC is already approved")

        ext = filename.rsplit(".", 1)[-1].lower()
        content_type = _EXT_TO_MIME.get(ext, "application/octet-stream")
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        key = f"kyc/{organization.id}/{timestamp}_{sanitize_filename(filename)}"

        try:
            uploaded_key = await self._storage.upload_file(file, key, content_type)
        except Exception as e:
            logger.error("KYC document upload failed for user %s: %s", user_id, e)
            raise ValidationException(
                message="File upload failed. Please try again."
            ) from e

        doc = await self._repo.save_kyc_document(
            organization_id=organization.id,
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
        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()

        current_status = organization.kyc_status or KYCStatus.NOT_SUBMITTED.value
        if current_status in (KYCStatus.PENDING.value, KYCStatus.APPROVED.value):
            raise PermissionDeniedException(
                message="Cannot delete documents while KYC is pending or approved"
            )

        doc = await self._repo.get_kyc_document(document_id)
        if doc is None:
            raise DocumentNotFoundError()
        if doc.organization_id != organization.id:
            raise PermissionDeniedException()

        await self._storage.delete_file(doc.key)
        await self._repo.delete_kyc_document(doc)
        await self._db.commit()

    async def generate_kyc_document_url(
        self, user_id: uuid.UUID, document_id: uuid.UUID
    ) -> str:
        """Generate a 15-minute presigned URL for a KYC document."""
        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()

        doc = await self._repo.get_kyc_document(document_id)
        if doc is None:
            raise DocumentNotFoundError()
        if doc.organization_id != organization.id:
            raise PermissionDeniedException()

        return await self._storage.generate_presigned_url(doc.key, 60 * 15)

    async def submit_kyc(self, user_id: uuid.UUID) -> KYCStatusResponse:
        """Flip kyc_status to PENDING. Requires at least one document uploaded."""
        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()

        current_status = organization.kyc_status or KYCStatus.NOT_SUBMITTED.value
        if current_status == KYCStatus.PENDING.value:
            raise KYCAlreadySubmittedException()
        if current_status == KYCStatus.APPROVED.value:
            raise KYCAlreadySubmittedException(message="KYC is already approved")

        if not organization.kyc_documents:
            raise ValidationException(
                message="Upload at least one document before submitting for verification"
            )

        await self._repo.set_kyc_status(organization, KYCStatus.PENDING.value)

        from app.modules.employer.tasks import send_kyc_submission_notification_email
        from app.modules.notifications.repository import NotificationRepository

        admins = await self._repo.list_admin_users()
        notification_repo = NotificationRepository(self._db)
        for admin in admins:
            send_kyc_submission_notification_email.delay(
                admin_email=admin.email,
                company_name=organization.company_name,
                organization_id=str(organization.id),
            )
            await notification_repo.create(
                recipient_id=admin.id,
                type="KYC_SUBMITTED",
                title=f"{organization.company_name or 'An employer'} submitted KYC documents",
                body="Review their documents to approve or reject verification.",
                entity_type="ORGANIZATION",
                entity_id=organization.id,
            )

        await self._db.commit()

        return KYCStatusResponse(
            kyc_status=organization.kyc_status,
            kyc_rejection_reason=organization.kyc_rejection_reason,
            kyc_submitted_at=organization.kyc_submitted_at,
            kyc_reviewed_at=organization.kyc_reviewed_at,
            documents=[
                KYCDocumentResponse.model_validate(d)
                for d in organization.kyc_documents
            ],
        )

    # ------------------------------------------------------------------
    # Team membership
    # ------------------------------------------------------------------

    async def list_team_members(self, user_id: uuid.UUID) -> list[TeamMemberResponse]:
        """List every member of the caller's organization."""
        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()
        members = await self._repo.list_members(organization.id)
        return [TeamMemberResponse.model_validate(m) for m in members]

    async def invite_team_member(self, user_id: uuid.UUID, email: str) -> str:
        """Invite a teammate into the caller's organization. Returns the raw invite token."""
        from app.modules.auth.service import AuthService

        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()

        auth_service = AuthService(self._db)
        return await auth_service.create_invite(
            email=email,
            inviter_id=user_id,
            organization_id=organization.id,
        )

    async def remove_team_member(
        self, user_id: uuid.UUID, target_user_id: uuid.UUID
    ) -> None:
        """Remove a teammate from the caller's organization.

        Refuses to remove the last remaining OWNER — someone has to be
        able to manage the organization's billing/team.
        """
        organization = await self._repo.get_organization_by_user_id(user_id)
        if organization is None:
            raise ProfileNotFoundException()

        target = await self._repo.get_member(organization.id, target_user_id)
        if target is None:
            raise NotFoundException(message="Team member not found")

        if target.organization_role == OrganizationRole.OWNER.value:
            owner_count = await self._repo.count_owners(organization.id)
            if owner_count <= 1:
                raise ValidationException(
                    message="Cannot remove the last owner of an organization"
                )

        target.organization_id = None
        target.organization_role = None
        await self._db.commit()
