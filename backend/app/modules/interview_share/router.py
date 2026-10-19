"""Endpoints for the shared interview results link.

For the people who make the link (signed in, employer or admin), under ``/interview-share``:
  GET    /jobs/{job_id}   the job's current link, if it has one
  POST   /jobs/{job_id}   make a new link (any earlier one stops working)
  DELETE /jobs/{job_id}   stop the link working

For whoever opens it (no login), under ``/public/interview-results``:
  GET    /{token}         the results, read-only
"""

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.limiter import limiter
from app.modules.interview_share.schemas import (
    SharedResults,
    ShareLinkResponse,
    ShareLinkStatus,
)
from app.modules.interview_share.service import InterviewShareService
from app.modules.users.models import User

router = APIRouter()
public_router = APIRouter()


@router.get("/jobs/{job_id}", response_model=ShareLinkStatus)
async def get_share_link(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
):
    return await InterviewShareService(db).get_status(current_user, job_id)


@router.post("/jobs/{job_id}", response_model=ShareLinkResponse, status_code=201)
async def create_share_link(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
):
    return await InterviewShareService(db).create(current_user, job_id)


@router.delete("/jobs/{job_id}", status_code=204)
async def revoke_share_link(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
):
    await InterviewShareService(db).revoke(current_user, job_id)
    return Response(status_code=204)


@public_router.get("/{token}", response_model=SharedResults)
@limiter.limit("30/minute")
async def get_shared_results(
    request: Request,
    response: Response,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    # Personal data and short-lived recording links: never stored by a browser or a proxy.
    response.headers["Cache-Control"] = "no-store"
    return await InterviewShareService(db).get_results(token)
