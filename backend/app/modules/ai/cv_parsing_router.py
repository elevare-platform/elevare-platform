"""HTTP endpoints for CV parsing — submit, list, download, and cost tracking."""

import uuid
from datetime import date

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis_client, require_role
from app.core.storage import StorageService, get_storage_service
from app.modules.ai.cv_parsing_service import CVParsingService
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.users.models import User

router = APIRouter()


async def get_cv_parsing_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis_client),
    storage: StorageService = Depends(get_storage_service),
) -> CVParsingService:
    """Build a CVParsingService with all injected dependencies."""
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
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    """Upload a single CV for parsing. Returns a ParsedCVSubmission record."""
    file_bytes = await file.read()
    return await service.submit_cv_for_parsing(
        current_user,
        file_bytes,
        file.filename,
    )


@router.get("/submissions", status_code=200)
async def get_submissions(
    request: Request,
    status: CVParsingStatus | None = None,
    cursor: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    """Return paginated CV parsing submissions. Employers see only their own."""
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
    """Return a single CV parsing submission by ID."""
    return await service.get_submission(id, current_user)


@router.get("/costs", status_code=200)
async def get_costs(
    current_user: User = Depends(require_role("ADMIN")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    """Return the current month's LLM cost summary. Admin only."""
    return await service.get_monthly_cost_summary()


@router.get("/costs/trend", status_code=200)
async def get_costs_trend(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    current_user: User = Depends(require_role("ADMIN")),
    service: CVParsingService = Depends(get_cv_parsing_service),
):
    """Return a monthly cost/call trend, optionally bounded by ?from=&to=
    (YYYY-MM-DD). Omit both for the full history. Admin only."""
    return await service.get_cost_trend(from_date, to_date)


@router.post("/submit/batch", status_code=201)
async def submit_pdf_batch(
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
    service: CVParsingService = Depends(get_cv_parsing_service),
    db: AsyncSession = Depends(get_db),
):
    """Upload up to 20 CVs for parsing in a single request. Professional+ —
    each file is its own CV-parsing LLM call, so a 20-file batch is the
    single most expensive thing an employer can trigger in one request.
    """
    if current_user.role != "ADMIN":
        from app.modules.billing.service import BillingService

        billing_service = BillingService(db)
        await billing_service.assert_professional_or_above(current_user.organization_id)

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
    """Generate a 15-minute presigned download URL for a parsed CV."""
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
