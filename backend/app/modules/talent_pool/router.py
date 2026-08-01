"""HTTP endpoints for the talent pool module."""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.limiter import limiter
from app.modules.talent_pool.schema import (
    TalentPoolProfileResponse,
    TalentPoolPromoteResponse,
    TalentPoolStatusUpdateRequest,
    TalentPoolSubmitRequest,
)
from app.modules.talent_pool.service import TalentPoolService
from app.modules.users.models import User

router = APIRouter()


def _get_talent_pool_service(db: AsyncSession = Depends(get_db)) -> TalentPoolService:
    """Build TalentPoolService with its CVParsingService dependency."""
    import redis.asyncio as aioredis

    from app.core.config import settings
    from app.core.storage import get_storage_service
    from app.modules.ai.cv_parsing_service import CVParsingService
    from app.modules.ai.service import get_ai_service

    redis = aioredis.from_url(settings.redis_url)
    cv_service = CVParsingService(
        db=db,
        storage=get_storage_service(),
        redis=redis,
        ai_service=get_ai_service(),
        nlp=None,  # not needed for submission, pipeline runs in Celery
    )
    return TalentPoolService(db=db, cv_service=cv_service)


def _user_id_key(request: Request) -> str:
    """Rate limit key based on authenticated user ID, not IP.

    Used for endpoints where per-user limiting is more appropriate than per-IP
    (e.g. employers behind a shared corporate proxy).
    """
    user = getattr(request.state, "user", None)
    if user:
        return str(user.id)
    from slowapi.util import get_remote_address

    return get_remote_address(request)


@router.post("/submit", response_model=TalentPoolProfileResponse, status_code=201)
async def submit_cv(
    file: UploadFile = File(...),
    source: str = Form(default="other"),
    source_note: str | None = Form(default=None),
    sourced_for_job_id: uuid.UUID | None = Form(default=None),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolProfileResponse:
    """Upload a single sourced CV into the talent pool."""
    data = TalentPoolSubmitRequest(
        source=source,
        source_note=source_note,
        sourced_for_job_id=sourced_for_job_id,
    )
    file_bytes = await file.read()
    return await service.submit(file_bytes, file.filename, data, current_user)


@router.post("/submit-batch", status_code=201)
@limiter.limit("20/hour", key_func=_user_id_key)
async def submit_cv_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    source: str = Form(default="other"),
    source_note: str | None = Form(default=None),
    sourced_for_job_id: uuid.UUID | None = Form(default=None),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> dict:
    """Upload multiple CVs into the talent pool in one request.

    Returns per-file status. Each file is processed independently —
    a failure on one does not affect others.
    """
    data = TalentPoolSubmitRequest(
        source=source,
        source_note=source_note,
        sourced_for_job_id=sourced_for_job_id,
    )
    file_pairs = [(await f.read(), f.filename) for f in files]
    results = await service.submit_batch(file_pairs, data, current_user)
    return {
        "total": len(results),
        "queued": sum(1 for r in results if r["status"] == "queued"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }


@router.get("", response_model=dict)
async def list_talent_pool(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    job_id: uuid.UUID | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> dict:
    """List talent pool profiles with optional filters."""
    return await service.list_profiles(
        status, source, job_id, cursor, limit, current_user
    )


@router.get("/{profile_id}", response_model=TalentPoolProfileResponse)
async def get_talent_pool_profile(
    profile_id: uuid.UUID,
    job_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolProfileResponse:
    """Return a single talent pool profile by ID.

    ``job_id`` is optional context — pass it when viewing this profile from
    a specific job's match list, so the AI assessment only shows if it's
    actually current for that job (see ``TalentPoolService.get_profile``).
    Omit it entirely for job-less contexts (e.g. Candidate Search).
    """
    return await service.get_profile(profile_id, current_user, job_id)


@router.patch("/{profile_id}/status", response_model=TalentPoolProfileResponse)
async def update_status(
    profile_id: uuid.UUID,
    data: TalentPoolStatusUpdateRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolProfileResponse:
    """Update the status of a talent pool profile."""
    return await service.update_status(profile_id, data)


@router.post("/{profile_id}/promote", response_model=TalentPoolPromoteResponse)
async def promote_to_candidate(
    profile_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolPromoteResponse:
    """Begin promotion — sends invite to candidate. Application created only after confirmation."""
    return await service.promote(profile_id, current_user)


@router.post("/score-against-job", status_code=202)
async def score_against_job(
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> dict:
    """Queue scoring for all unscored pipeline profiles against a given job.

    Returns immediately with a count of queued tasks — scoring runs in the background.
    """
    return await service.score_against_job(job_id)


@router.get("/matches/{job_id}/new-count", response_model=dict)
async def get_new_matches_count(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
) -> dict:
    """Return the number of new (unseen) matches for a job without consuming them.

    Use this to power the badge on the AI Recruiter tab before the employer opens it.
    """
    from app.modules.notifications.match_repository import MatchNotificationRepository

    repo = MatchNotificationRepository(db)
    count = await repo.count_new_for_job(job_id)
    return {"job_id": str(job_id), "new_count": count}


@router.get("/matches/{job_id}", response_model=dict)
async def get_job_matches(
    job_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> dict:
    """Return AI-matched talent pool profiles for a job, ranked by blended score.

    Also marks all new matches as viewed — call this endpoint to consume the new-match badge.
    """
    result = await service.get_job_matches(
        job_id=job_id,
        employer_id=current_user.id,
        limit=limit,
    )
    return result.model_dump()


@router.post("/{profile_id}/score", status_code=202)
async def score_profile_against_job(
    profile_id: uuid.UUID,
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> dict:
    """Queue scoring for a single talent pool profile against a given job.

    Returns immediately with a count of queued tasks — scoring runs in the background.
    """
    return await service.score_profile_against_job(profile_id, job_id, current_user)
