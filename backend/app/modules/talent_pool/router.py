import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
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


@router.post("/submit", response_model=TalentPoolProfileResponse, status_code=201)
async def submit_cv(
    file: UploadFile = File(...),
    source: str = Form(default="other"),
    source_note: str | None = Form(default=None),
    sourced_for_job_id: uuid.UUID | None = Form(default=None),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolProfileResponse:
    """Upload a sourced CV into the talent pool."""
    data = TalentPoolSubmitRequest(
        source=source,
        source_note=source_note,
        sourced_for_job_id=sourced_for_job_id,
    )
    file_bytes = await file.read()
    return await service.submit(file_bytes, file.filename, data, current_user)


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
    return await service.list_profiles(status, source, job_id, cursor, limit)


@router.get("/{profile_id}", response_model=TalentPoolProfileResponse)
async def get_talent_pool_profile(
    profile_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolProfileResponse:
    return await service.get_profile(profile_id)


@router.patch("/{profile_id}/status", response_model=TalentPoolProfileResponse)
async def update_status(
    profile_id: uuid.UUID,
    data: TalentPoolStatusUpdateRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolProfileResponse:
    return await service.update_status(profile_id, data)


@router.post("/{profile_id}/promote", response_model=TalentPoolPromoteResponse)
async def promote_to_candidate(
    profile_id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN")),
    service: TalentPoolService = Depends(_get_talent_pool_service),
) -> TalentPoolPromoteResponse:
    """Begin promotion — sends invite to candidate. Application created only after confirmation."""
    return await service.promote(profile_id, current_user)
