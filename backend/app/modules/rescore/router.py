"""Endpoints for rescoring a job's candidates who have no usable score.

Employers (their own organization's jobs) and admins:
  GET  /jobs/{job_id}   how many of the job's candidates could be rescored
  POST /jobs/{job_id}   rescore one candidate (send an id) or everyone who needs it,
                        a batch at a time. Paid plans only: every candidate rescored
                        is a model call.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.limiter import limiter
from app.modules.rescore.schemas import RescoreRequest, RescoreResult, RescoreStatus
from app.modules.rescore.service import RescoreService
from app.modules.users.models import User

router = APIRouter()

EmployerOrAdmin = Depends(require_role("EMPLOYER", "ADMIN"))


@router.get("/jobs/{job_id}", response_model=RescoreStatus)
async def get_rescore_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = EmployerOrAdmin,
):
    return await RescoreService(db).status(current_user, job_id)


@router.post("/jobs/{job_id}", response_model=RescoreResult)
@limiter.limit("10/minute")
async def rescore_job(
    request: Request,
    job_id: uuid.UUID,
    data: RescoreRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = EmployerOrAdmin,
):
    return await RescoreService(db).rescore(current_user, job_id, data or RescoreRequest())
