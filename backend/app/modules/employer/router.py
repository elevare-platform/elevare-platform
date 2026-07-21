"""HTTP endpoints for employer-specific operations."""

import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.core.storage import StorageService, get_storage_service
from app.modules.employer.schemas import (
    EmployerStats,
    KYCDocumentResponse,
    KYCStatusResponse,
)
from app.modules.employer.service import EmployerService
from app.modules.users.models import User
from app.modules.users.schemas import (
    EmployerProfileResponse,
    EmployerProfileUpdateRequest,
)
from app.modules.users.service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()


def get_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> EmployerService:
    """Construct EmployerService with injected DB and storage."""
    return EmployerService(db, storage)


@router.get("/stats", response_model=EmployerStats, status_code=200)
async def get_employer_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
) -> EmployerStats:
    """Return job statistics for the authenticated employer."""
    return await EmployerService(db).get_employer_stats(current_user.id)


@router.patch("/profile", response_model=EmployerProfileResponse, status_code=200)
async def update_employer_profile(
    data: EmployerProfileUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
) -> EmployerProfileResponse:
    """Create or update the authenticated employer's company profile."""
    return await UserService(db).update_employer_profile(current_user.id, data)


@router.get("/profile", response_model=EmployerProfileResponse, status_code=200)
async def get_employer_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
) -> EmployerProfileResponse:
    """Return the authenticated employer's company profile."""
    return await UserService(db).get_employer_profile(current_user.id)


# ---------------------------------------------------------------------------
# KYC
# ---------------------------------------------------------------------------


@router.get("/kyc", response_model=KYCStatusResponse, status_code=200)
async def get_kyc_status(
    current_user: User = Depends(require_role("EMPLOYER")),
    service: EmployerService = Depends(get_service),
) -> KYCStatusResponse:
    """Return the KYC status and uploaded documents for the authenticated employer."""
    return await service.get_kyc_status(current_user.id)


@router.post("/kyc/documents", response_model=KYCDocumentResponse, status_code=201)
async def upload_kyc_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    current_user: User = Depends(require_role("EMPLOYER")),
    service: EmployerService = Depends(get_service),
) -> KYCDocumentResponse:
    """Upload a KYC document (Business Registration, Tax ID, or Proof of Address)."""
    contents = await file.read()
    return await service.upload_kyc_document(
        user_id=current_user.id,
        file=contents,
        filename=file.filename,
        document_type=document_type,
    )


@router.get(
    "/kyc/documents/{document_id}/url",
    response_model=SuccessResponse,
    status_code=200,
)
async def get_kyc_document_url(
    document_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER")),
    service: EmployerService = Depends(get_service),
) -> SuccessResponse:
    """Generate a 15-minute presigned URL for a KYC document."""
    url = await service.generate_kyc_document_url(current_user.id, document_id)
    return SuccessResponse(message="URL generated", data={"url": url})


@router.delete(
    "/kyc/documents/{document_id}",
    response_model=SuccessResponse,
    status_code=200,
)
async def delete_kyc_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER")),
    service: EmployerService = Depends(get_service),
) -> SuccessResponse:
    """Delete a KYC document. Only allowed when status is NOT_SUBMITTED or REJECTED."""
    await service.delete_kyc_document(current_user.id, document_id)
    return SuccessResponse(message="Document deleted")


@router.post("/kyc/submit", response_model=KYCStatusResponse, status_code=200)
async def submit_kyc(
    current_user: User = Depends(require_role("EMPLOYER")),
    service: EmployerService = Depends(get_service),
) -> KYCStatusResponse:
    """Submit KYC documents for admin review. Flips status to PENDING."""
    return await service.submit_kyc(current_user.id)
