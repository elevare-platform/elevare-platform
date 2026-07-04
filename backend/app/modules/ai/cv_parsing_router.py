from app.core.exceptions import SubmissionNotFound
import uuid

from app.modules.ai.enums import CVParsingStatus
from app.modules.users.models import User
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.ai.cv_parsing_service import CVParsingService
from app.core.storage import get_storage_service
from app.core.storage import StorageService
from app.core.dependencies import get_redis_client
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.requests import Request
from fastapi import APIRouter, Depends, UploadFile, File
from app.core.dependencies import get_db, require_role
import redis.asyncio as aioredis

router = APIRouter()

async def get_cv_parsing_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
    storage: StorageService = Depends(get_storage_service),
) -> CVParsingService:
    return CVParsingService(
        db=db,
        storage=storage,
        redis=redis,
        ai_service=AnthropicCVExtractionService(),
        nlp=getattr(request.app.state, "nlp", None),
    )

@router.post("/submit", status_code=201)
async def submit_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service)
):
    file_bytes = await file.read()
    submission = await service.submit_cv_for_parsing(
        current_user,
        file_bytes,
        file.filename,
    )
    return submission

@router.get("/submissions", status_code=200)
async def get_submissions(
    request: Request,
    status: CVParsingStatus | None = None,
    cursor: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    return await service.list_submissions(
        current_user,
        status=status,
        cursor=cursor,
        limit=limit,
    )

@router.get("/submissions/{id}", status_code=200)
async def get_submission(
    id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    return await service.get_submission(id, current_user)

@router.get("/costs", status_code=200)
async def get_costs(
    current_user: User = Depends(require_role("ADMIN")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    return await service.get_monthly_cost_summary()

# TODO: MAKE THIS A PRO PLAN WHERE HR CAN BATCH ADD MULTIPLE PDFS AT ONCE
@router.post("/submit/batch", status_code=201)
async def submit_pdf_batch(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    if len(files) > 20:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch")

    results = []
    for file in files:
        file_bytes = await file.read()
        submission = await service.submit_cv_for_parsing(
            current_user, file_bytes, file.filename
        )
        results.append(submission)
    return results

@router.get("/submissions/{id}/download", status_code=200)
async def download_cv(
    request: Request,
    id: uuid.UUID,
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    return await service.generate_cv_url(id, current_user)

@router.post("/submissions/{id}/create-candidate", status_code=410)
async def create_candidate_from_submission(id: uuid.UUID):
    """Deprecated — removed in Phase 11.5.

    All externally-sourced CVs now land in TalentPoolProfile.
    Use POST /talent-pool/submit instead.
    """
    from fastapi import HTTPException
    raise HTTPException(
        status_code=410,
        detail="This endpoint has been removed. Use POST /api/v1/talent-pool/submit instead.",
    )

