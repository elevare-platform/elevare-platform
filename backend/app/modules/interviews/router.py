"""HTTP endpoints for the interviews module."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_candidate, get_db, require_role
from app.core.limiter import limiter
from app.modules.candidates.models import CandidateProfile
from app.modules.interviews.schema import (
    InterviewCompleteRequest,
    InterviewDetailResponse,
    InterviewInviteBulkSendResponse,
    InterviewInviteSendResponse,
    InterviewPublicInfoResponse,
    InterviewResetRequestResponse,
    InterviewResponse,
    InterviewSessionResponse,
    InterviewUploadUrlResponse,
)
from app.modules.interviews.service import InterviewService
from app.modules.users.models import User

# ─── Authenticated candidate routes — resolved via application_id + login ───

router = APIRouter()


@router.post(
    "/applications/{application_id}/session",
    status_code=201,
    response_model=InterviewSessionResponse,
)
async def create_interview_session(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionResponse:
    """Candidate starts (or reconnects to) their live AI video interview.

    Returns a short-lived Realtime API client secret — the browser connects
    directly to OpenAI with it, the live audio never passes through our
    servers.
    """
    service = InterviewService(db)
    try:
        return await service.create_session(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/request-reset",
    status_code=200,
    response_model=InterviewResetRequestResponse,
)
async def request_interview_reset(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewResetRequestResponse:
    """Candidate locked out by the restart lock asks the employer to reset it."""
    service = InterviewService(db)
    try:
        return await service.request_reset(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/upload-url",
    status_code=201,
    response_model=InterviewUploadUrlResponse,
)
async def create_upload_url(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewUploadUrlResponse:
    """Candidate requests a presigned URL to upload their recording directly to R2."""
    service = InterviewService(db)
    try:
        return await service.generate_upload_url(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/complete",
    status_code=200,
    response_model=InterviewResponse,
)
async def complete_interview_upload(
    application_id: uuid.UUID,
    body: InterviewCompleteRequest = InterviewCompleteRequest(),
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewResponse:
    """Candidate confirms the recording finished uploading to R2."""
    service = InterviewService(db)
    try:
        return await service.complete_upload(
            application_id=application_id,
            candidate_id=candidate.user_id,
            transcript=body.transcript,
            realtime_usage=body.realtime_usage,
        )
    finally:
        await service.close()


@router.get(
    "/applications/{application_id}",
    status_code=200,
    response_model=InterviewResponse,
)
async def get_interview(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewResponse:
    """Candidate views the status of their interview for an application."""
    service = InterviewService(db)
    try:
        return await service.get_for_application(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()

@router.post("/{talent_pool_profile_id}/send-invite", response_model=InterviewInviteSendResponse, status_code=200)
async def send_interview_invite(
    talent_pool_profile_id: uuid.UUID,
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly send (or resend) an AI interview invite to one candidate."""
    service = InterviewService(db)
    try:
        return await service.send_invite(current_user.id, job_id, talent_pool_profile_id)
    finally:
        await service.close()


@router.post("/send-invites", response_model=InterviewInviteBulkSendResponse, status_code=200)
async def send_interview_invites_to_all(
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly send (or resend) AI interview invites to everyone on this job's interview list."""
    service = InterviewService(db)
    try:
        return await service.send_invites_to_all(current_user.id, job_id)
    finally:
        await service.close()


@router.get("/detail", response_model=InterviewDetailResponse, status_code=200)
async def get_interview_detail(
    job_id: uuid.UUID = Query(...),
    talent_pool_profile_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Employer views transcript/score/video for one candidate's completed interview."""
    service = InterviewService(db)
    try:
        return await service.get_detail_for_employer(
            current_user.id, job_id, talent_pool_profile_id
        )
    finally:
        await service.close()


@router.get("/costs", status_code=200)
async def get_interview_costs(
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return the current month's interview cost summary, broken down by
    component (realtime/transcription/scoring). Admin only."""
    service = InterviewService(db)
    try:
        return await service.get_monthly_cost_summary()
    finally:
        await service.close()


@router.get("/costs/trend", status_code=200)
async def get_interview_costs_trend(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return a monthly interview cost/call trend, broken down by component,
    optionally bounded by ?from=&to= (YYYY-MM-DD). Omit both for the full
    history. Admin only."""
    service = InterviewService(db)
    try:
        return await service.get_cost_trend(from_date, to_date)
    finally:
        await service.close()


# ─── Public token routes — no login required, reached from an emailed link ──
#
# Being added to a job's interview list is what grants access, not having
# an Elevare account — sourced/parsed profiles reach these from an emailed
# magic link instead of a Bearer token.

public_router = APIRouter()


@public_router.get(
    "/{token}",
    status_code=200,
    response_model=InterviewPublicInfoResponse,
)
@limiter.limit("30/minute")
async def get_interview_invite_info(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewPublicInfoResponse:
    """Job/company context for the consent screen, before the candidate starts."""
    service = InterviewService(db)
    try:
        return await service.get_public_info(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/session",
    status_code=201,
    response_model=InterviewSessionResponse,
)
@limiter.limit("10/minute")
async def create_interview_session_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionResponse:
    """Start (or reconnect to) the live AI video interview from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.create_session_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/request-reset",
    status_code=200,
    response_model=InterviewResetRequestResponse,
)
@limiter.limit("5/minute")
async def request_interview_reset_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewResetRequestResponse:
    """No-login candidate locked out by the restart lock asks the employer to reset it."""
    service = InterviewService(db)
    try:
        return await service.request_reset_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/upload-url",
    status_code=201,
    response_model=InterviewUploadUrlResponse,
)
@limiter.limit("10/minute")
async def create_upload_url_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewUploadUrlResponse:
    """Request a presigned upload URL from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.generate_upload_url_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/complete",
    status_code=200,
    response_model=InterviewResponse,
)
@limiter.limit("10/minute")
async def complete_interview_upload_by_token(
    request: Request,
    token: str,
    body: InterviewCompleteRequest = InterviewCompleteRequest(),
    db: AsyncSession = Depends(get_db),
) -> InterviewResponse:
    """Confirm the recording finished uploading, from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.complete_upload_by_token(
            token, transcript=body.transcript, realtime_usage=body.realtime_usage
        )
    finally:
        await service.close()
