"""HTTP endpoints for the jobs module."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_optional_user, require_role
from app.modules.introductions.router import router as intro_router
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
router.include_router(intro_router)


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
    search: str | None = None,
    status_filter: str = Query(default="active", alias="filter"),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobListResponse:
    """Return jobs owned by the authenticated employer (or admin).

    Must be declared before /{job_id} to prevent route conflict.
    ``search`` filters by job title (case-insensitive substring match).
    ``filter`` buckets by status: active (default) | pending | rejected | closed | all.
    """
    return await JobService(db).list_employer_jobs(
        employer=current_user,
        cursor=cursor,
        limit=limit,
        search=search,
        status_filter=status_filter,
    )


@router.post("/general-interest", response_model=JobResponse, status_code=200)
async def get_or_create_general_interest_job(
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Return (creating if needed) the employer's "General Interest" placeholder job.

    Anchors an introduction/notify request from Candidate Search when the
    employer has no real job postings yet. Must be declared before
    /{job_id} to prevent route conflict.
    """
    return await JobService(db).get_or_create_general_interest_job(current_user.id)


@router.get("/{job_id}", response_model=JobResponse, status_code=200)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> JobResponse:
    """Return a single job by ID.

    Public for published jobs — a DRAFT job (unpublished, or pulled offline
    for re-review) is only visible to its owning employer or an admin.
    """
    return await JobService(db).get_job_by_id(job_id, requesting_user=current_user)


# ---------------------------------------------------------------------------
# Employer endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreateRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Create a new draft job. Employer or admin."""
    return await JobService(db).create_job(data, employer=current_user)


@router.patch("/{job_id}", response_model=JobResponse, status_code=200)
async def update_job(
    job_id: UUID,
    data: JobUpdateRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Update a job partially. Owning employer or admin (any job)."""
    return await JobService(db).update_job(job_id, data, current_user)


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a draft job. Owning employer or admin (any job).

    Only DRAFT jobs can be deleted — a job that was ever published must be
    closed instead, since it may already have applications or matches.
    """
    await JobService(db).delete_job(job_id, current_user)


@router.post("/{job_id}/resubmit", response_model=JobResponse, status_code=200)
async def resubmit_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Resubmit a REJECTED job for another admin review. Owning employer or admin (any job)."""
    return await JobService(db).resubmit_job(job_id, current_user)


@router.post("/{job_id}/publish", response_model=JobResponse, status_code=200)
async def publish_job(
    job_id: UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Publish a draft job (DRAFT → ACTIVE). Owning employer or admin (any job)."""
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


@router.get(
    "/{job_id}/talent-matches", response_model=TalentMatchListResponse, status_code=200
)
async def get_talent_matches(
    job_id: UUID,
    limit: int = Query(default=20, ge=3, le=50),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> TalentMatchListResponse:
    """Return AI-matched talent pool profiles for a job. Employer or admin."""
    import redis.asyncio as aioredis

    from app.core.config import settings
    from app.core.storage import get_storage_service
    from app.modules.ai.cv_parsing_service import CVParsingService
    from app.modules.ai.service import get_ai_service
    from app.modules.talent_pool.service import TalentPoolService

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
        is_admin=current_user.role == "ADMIN",
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
