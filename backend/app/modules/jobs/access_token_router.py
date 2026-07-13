"""HTTP endpoints for job access tokens and public applicant views."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.modules.jobs.access_token_schema import (
    AccessTokenResponse,
    CreateAccessTokenRequest,
    PublicApplicantsResponse,
)
from app.modules.jobs.access_token_service import AccessTokenService
from app.modules.users.models import User

router = APIRouter()


@router.post(
    "/jobs/{job_id}/access-tokens", response_model=AccessTokenResponse, status_code=201
)
async def create_access_token(
    job_id: uuid.UUID,
    data: CreateAccessTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
) -> AccessTokenResponse:
    """Generate a shareable cleint link for a job's applicant's list."""
    service = AccessTokenService(db)
    return await service.create_access_token(job_id, data, current_user)


@router.get("/jobs/{job_id}/access-tokens", response_model=list[AccessTokenResponse])
async def get_access_tokens(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> list[AccessTokenResponse]:
    """Return all access tokens for a job."""
    service = AccessTokenService(db)
    return await service.get_all_access_tokens(job_id, current_user)


@router.delete("/jobs/{job_id}/access-tokens/{token_id}", status_code=204)
async def delete_access_token(
    job_id: uuid.UUID,
    token_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    db: AsyncSession = Depends(get_db),
):
    """Delete a job access token. Only the job owner or an admin can delete."""
    service = AccessTokenService(db)
    await service.delete_access_token(job_id, token_id, current_user)
    return SuccessResponse(message="Access token deleted successfully")


@router.patch(
    "/jobs/access-tokens/{token_id}/revoke", response_model=AccessTokenResponse
)
async def revoke_access_token(
    token_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """Immediately revoke a shareable link."""
    return await AccessTokenService(db).revoke_token(token_id, current_user)


@router.get("/public/jobs/{token}/applicants", response_model=PublicApplicantsResponse)
async def public_applicants(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PublicApplicantsResponse:
    """Public ranked applicant view — no auth required.

    Returns 404 for invalid, expired, or revoked tokens.
    """
    return await AccessTokenService(db).get_public_applicants(token)
