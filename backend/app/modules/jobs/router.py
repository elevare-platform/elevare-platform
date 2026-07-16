"""HTTP endpoints for the jobs module."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.jobs.schemas import (
    JobCreateRequest,
    JobFilterParams,
    JobListResponse,
    JobResponse,
    JobUpdateRequest,
)
from app.modules.jobs.service import JobService
from app.modules.talent_pool.schema import TalentMatchListResponse
from app.modules.users.models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=JobListResponse, status_code=200)
async def list_jobs(
    filters: JobFilterParams = Depends(),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """List active jobs with optional filters and cursor pagination.

    Public — no authentication required.
    """
    return await JobService(db).list_jobs(
        filters=filters,
        cursor=filters.cursor,
        limit=filters.limit,
    )


@router.get("/mine", response_model=JobListResponse, status_code=200)
async def list_my_jobs(
    cursor: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """Return all jobs owned by the authenticated employer.

    Must be declared before /{job_id} to prevent route conflict.
    """
    return await JobService(db).list_employer_jobs(
        employer=current_user,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{job_id}", response_model=JobResponse, status_code=200)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Return a single job by ID. Public — no authentication required."""
    return await JobService(db).get_job_by_id(job_id)


# ---------------------------------------------------------------------------
# Employer endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreateRequest,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new draft job. Employer only."""
    return await JobService(db).create_job(data, employer=current_user)


@router.patch("/{job_id}", response_model=JobResponse, status_code=200)
async def update_job(
    job_id: UUID,
    data: JobUpdateRequest,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Update a job partially. Only the owning employer can modify it."""
    return await JobService(db).update_job(job_id, data, current_user)


@router.post("/{job_id}/publish", response_model=JobResponse, status_code=200)
async def publish_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Publish a draft job (DRAFT → ACTIVE). Only the owning employer."""
    return await JobService(db).publish_job(job_id, current_user)


@router.post("/{job_id}/close", response_model=JobResponse, status_code=200)
async def close_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Close a job (ACTIVE → CLOSED). Employer (own jobs) or Admin (any job)."""
    return await JobService(db).close_job(job_id, current_user)


@router.post("/{job_id}/cv-upload", status_code=201)
async def upload_cvs_for_job(
    job_id: UUID,
    files: list[UploadFile] = File(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Employer uploads CVs received externally for their own job.

    CVs are parsed and scored against this job. Results are stored as
    employer-scoped ParsedCVSubmissions — they are NOT added to the
    global talent pipeline. Ownership enforced: only the job's employer
    or an admin can upload.
    """
    import redis.asyncio as aioredis

    from app.core.config import settings
    from app.core.exceptions import JobNotFoundError, PermissionDeniedException
    from app.core.storage import get_storage_service
    from app.modules.ai.cv_parsing_service import CVParsingService
    from app.modules.ai.service import get_ai_service
    from app.modules.jobs.repository import JobRepository

    job_repo = JobRepository(db)
    job = await job_repo.get_by_id(job_id)
    if not job:
        raise JobNotFoundError()
    if current_user.role != "ADMIN" and job.employer_id != current_user.id:
        raise PermissionDeniedException("You do not own this job")

    redis = aioredis.from_url(settings.redis_url)
    cv_service = CVParsingService(
        db=db,
        storage=get_storage_service(),
        redis=redis,
        ai_service=get_ai_service(),
        nlp=None,
    )

    results = []
    for upload in files:
        file_bytes = await upload.read()
        try:
            submission = await cv_service.submit_cv_for_parsing(
                uploaded_by=current_user,
                file=file_bytes,
                filename=upload.filename,
            )
            results.append(
                {
                    "filename": upload.filename,
                    "submission_id": str(submission.id),
                    "status": "queued",
                }
            )
        except Exception as e:
            results.append(
                {"filename": upload.filename, "status": "failed", "error": str(e)}
            )

    return {"uploaded": len(results), "results": results}

@router.get("/{job_id}/talent-matches", response_model=TalentMatchListResponse, status_code=200)
async def get_talent_matches(
    job_id: UUID,
    limit: int = Query(default=20, ge=3, le=50),
    current_user: User = Depends(require_role("EMPLOYER")),
    db: AsyncSession = Depends(get_db),
) -> TalentMatchListResponse:
    """Return AI-matched talent pool profiles for a job. Employer only.
    """
    from app.modules.talent_pool.service import TalentPoolService
    from app.modules.talent_pool.schema import TalentMatchListResponse
    from app.modules.ai.cv_parsing_service import CVParsingService
    from app.core.storage import get_storage_service
    import redis.asyncio as aioredis
    from app.core.config import settings
    from app.modules.ai.service import get_ai_service

    redis = aioredis.from_url(settings.redis_url)

    cv_service = CVParsingService(
        db=db,
        storage=get_storage_service(),
        redis=redis,
        ai_service=get_ai_service(),
        nlp=None,
    )

    return await TalentPoolService(db, cv_service).get_job_matches(
        job_id=job_id,
        limit=limit,
        employer_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/admin/jobs", response_model=JobListResponse, status_code=200)
async def admin_list_jobs(
    cursor: str | None = None,
    limit: int = 20,
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """Return all jobs regardless of status. Admin only."""
    return await JobService(db).admin_list_jobs(cursor=cursor, limit=limit)
