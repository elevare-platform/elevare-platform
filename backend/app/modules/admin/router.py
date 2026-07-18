"""HTTP endpoints for admin operations."""

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.core.storage import StorageService, get_storage_service
from app.modules.auth.service import AuthService
from app.modules.testimonials.enums import TestimonialStatus
from app.modules.testimonials.schemas import (
    TestimonialAdminRead,
    TestimonialModerationRequest,
)
from app.modules.testimonials.service import TestimonialService
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import User

from .schemas import (
    BulkJobActionRequest,
    BulkUserActionRequest,
    CreditGrantRequest,
    InviteRequest,
    JobModerationRequest,
    UserStatusUpdateRequest,
)
from .service import AdminService

router = APIRouter()


# ---------------------------------------------------------------------------
# Invites (existing endpoints)
# ---------------------------------------------------------------------------


@router.post("/employers/invite", status_code=200)
async def create_invite(
    data: InviteRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Create an employer invite. Returns the raw token in stub mode."""
    service = AuthService(db)
    raw_token = await service.create_invite(data.email, data.role.value, admin_user.id)
    if settings.email_stub_mode:
        return {"invite_token": raw_token}
    return SuccessResponse(message="Invite sent")


@router.post("/employers/invite/{token}/resend", status_code=200)
async def resend_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Invalidate an existing invite and issue a new one."""
    service = AuthService(db)
    raw_token = await service.resend_invite(token, admin_user.id)
    if settings.email_stub_mode:
        return {"invite_token": raw_token}
    return SuccessResponse(message="Invite resent")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", status_code=200)
async def list_users(
    role: UserRole | None = Query(default=None),
    status: AccountStatus | None = Query(default=None),
    search: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """List users with optional filters and pagination."""
    service = AdminService(db)
    return await service.list_users(
        role=role.value if role else None,
        status=status.value if status else None,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.get("/users/{user_id}", status_code=200)
async def get_user_detail(
    user_id: UUID = Path(...),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Get detailed information about a specific user."""
    service = AdminService(db)
    return await service.get_user_detail(user_id=user_id)


@router.patch("/users/{user_id}", status_code=200)
async def update_user_status(
    user_id: UUID = Path(...),
    data: UserStatusUpdateRequest = ...,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Update a user's account status."""
    service = AdminService(db)
    return await service.update_user_status(
        admin_id=admin_user.id,
        user_id=user_id,
        new_status=data.status.value,
    )


@router.patch("/users/bulk", status_code=200)
async def bulk_update_users(
    data: BulkUserActionRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Bulk update user statuses (max 100)."""
    service = AdminService(db)
    return await service.bulk_update_user_status(
        admin_id=admin_user.id,
        user_ids=data.user_ids,
        action=data.action,
    )


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


@router.get("/jobs", status_code=200)
async def list_jobs(
    status: str | None = Query(default=None),
    moderation_status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """List all jobs with optional filters."""
    service = AdminService(db)
    return await service.list_jobs(
        status=status,
        moderation_status=moderation_status,
        search=search,
        cursor=cursor,
        limit=limit,
    )


@router.patch("/jobs/{job_id}/moderate", status_code=200)
async def moderate_job(
    job_id: UUID = Path(...),
    data: JobModerationRequest = ...,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Approve, reject, or close a job listing."""
    service = AdminService(db)
    return await service.moderate_job(
        admin_id=admin_user.id, job_id=job_id, action=data.action, reason=data.reason
    )


@router.patch("/jobs/bulk", status_code=200)
async def bulk_update_jobs(
    data: BulkJobActionRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Bulk update job statuses (max 100)."""
    service = AdminService(db)
    return await service.bulk_update_job_status(
        admin_id=admin_user.id,
        job_ids=data.job_ids,
        action=data.action,
    )


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


@router.get("/applications", status_code=200)
async def list_applications(
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """List all applications platform-wide."""
    service = AdminService(db)
    return await service.list_applications(
        status=status,
        cursor=cursor,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@router.get("/stats", status_code=200)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Get platform-wide statistics."""
    service = AdminService(db)
    return await service.get_platform_stats()


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


@router.get("/export/applications", status_code=200)
async def export_applications(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Export all applications as CSV."""
    service = AdminService(db)
    csv_content = await service.export_applications_csv()
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=applications.csv"},
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@router.get("/settings", status_code=200)
async def get_settings(
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Return current platform settings visible to admins."""
    return {
        "show_ai_score_to_candidates": settings.show_ai_score_to_candidates,
        "default_access_token_expiry_days": settings.default_access_token_expiry_days,
    }


@router.patch("/settings/ai-score-visibility", status_code=200)
async def toggle_ai_score_visibility(
    enabled: bool,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Toggle whether candidates can see their ai_score. Writes an audit log entry."""
    old_value = settings.show_ai_score_to_candidates
    # Runtime toggle — affects the in-memory settings object for this process.
    # A deploy/restart resets to the env value, which is intentional.
    settings.show_ai_score_to_candidates = enabled

    service = AdminService(db)
    await service._repo.write_audit_log(
        admin_id=admin_user.id,
        action="toggled_ai_score_visibility",
        reason=None,
        target_type="platform_settings",
        target_id=admin_user.id,  # no specific target — use admin's own id as a placeholder
        log_metadata={"old_value": old_value, "new_value": enabled},
    )
    await db.commit()

    return {"show_ai_score_to_candidates": settings.show_ai_score_to_candidates}


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


@router.get("/audit-log", status_code=200)
async def list_audit_log(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Get audit log entries."""
    service = AdminService(db)
    return await service.list_audit_log(cursor=cursor, limit=limit)


# ---------------------------------------------------------------------------
# Testimonials
# ---------------------------------------------------------------------------


def get_testimonial_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> TestimonialService:
    return TestimonialService(db, storage_service)


@router.get("/testimonials", response_model=list[TestimonialAdminRead], status_code=200)
async def admin_list_testimonials(
    status: TestimonialStatus | None = Query(default=None),
    admin_user: User = Depends(require_role("ADMIN")),
    service: TestimonialService = Depends(get_testimonial_service),
) -> list[TestimonialAdminRead]:
    """List all testimonials. Filter by status using ?status=pending|approved|rejected."""
    return await service.admin_list_testimonials(status)


@router.patch(
    "/testimonials/{testimonial_id}",
    response_model=TestimonialAdminRead,
    status_code=200,
)
async def moderate_testimonial(
    testimonial_id: UUID = Path(...),
    data: TestimonialModerationRequest = ...,
    admin_user: User = Depends(require_role("ADMIN")),
    service: TestimonialService = Depends(get_testimonial_service),
) -> TestimonialAdminRead:
    """Approve, reject, or reset a testimonial back to pending."""
    return await service.moderate_testimonial(testimonial_id, data)


@router.post("/maintenance/reindex-ai", status_code=200)
async def reindex_ai(
    admin_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """One-off maintenance endpoint — resets all AI hashes and re-queues:

    1. Embedding regeneration for all candidate profiles, talent pool profiles,
       and active jobs (new work-history-based embeddings).
    2. Score recomputation for all applications and talent pool profiles
       (new LLM-first scoring against structured job fields).

    Safe to call multiple times — idempotent. Celery tasks skip work when
    content hasn't changed, but since hashes are cleared here they will always
    run at least once.
    """
    from sqlalchemy import select, update

    from app.modules.ai.tasks import (
        generate_candidate_embedding_task,
        generate_job_embedding_task,
        generate_talent_pool_embedding_task,
        score_application_task,
        score_talent_pool_profile_task,
    )
    from app.modules.applications.models import Application
    from app.modules.candidates.models import CandidateProfile
    from app.modules.jobs.enums import JobStatus
    from app.modules.jobs.models import Job
    from app.modules.talent_pool.models import TalentPoolProfiles

    # ── 1. Clear embedding hashes ──────────────────────────────────────────
    await db.execute(update(CandidateProfile).values(embedding_source_hash=None))
    await db.execute(update(TalentPoolProfiles).values(embedding_source_hash=None))
    await db.execute(
        update(Job)
        .where(Job.status == JobStatus.ACTIVE.value)
        .values(embedding_source_hash=None)
    )

    # ── 2. Clear scoring hashes ────────────────────────────────────────────
    await db.execute(
        update(Application).values(
            ai_score_job_hash=None,
            ai_score_cv_hash=None,
        )
    )
    await db.execute(
        update(TalentPoolProfiles).values(
            ai_score_job_hash=None,
            ai_score_cv_hash=None,
        )
    )

    await db.commit()

    # ── 3. Fetch IDs and queue Celery tasks ────────────────────────────────
    candidate_ids = (await db.execute(select(CandidateProfile.id))).scalars().all()
    tp_ids = (await db.execute(select(TalentPoolProfiles.id))).scalars().all()
    job_ids = (
        (await db.execute(select(Job.id).where(Job.status == JobStatus.ACTIVE.value)))
        .scalars()
        .all()
    )
    application_ids = (await db.execute(select(Application.id))).scalars().all()
    tp_with_job = (
        await db.execute(
            select(TalentPoolProfiles.id, TalentPoolProfiles.sourced_for_job_id).where(
                TalentPoolProfiles.sourced_for_job_id.is_not(None)
            )
        )
    ).all()

    for cid in candidate_ids:
        generate_candidate_embedding_task.delay(str(cid))

    for tid in tp_ids:
        generate_talent_pool_embedding_task.delay(str(tid))

    for jid in job_ids:
        generate_job_embedding_task.delay(str(jid))

    for aid in application_ids:
        score_application_task.delay(str(aid))

    for tp_id, job_id in tp_with_job:
        score_talent_pool_profile_task.delay(str(tp_id), str(job_id))

    return {
        "status": "queued",
        "candidates": len(candidate_ids),
        "talent_pool_profiles": len(tp_ids),
        "active_jobs": len(job_ids),
        "applications": len(application_ids),
        "talent_pool_scored": len(tp_with_job),
    }


# ---------------------------------------------------------------------------
# Credits
# ---------------------------------------------------------------------------


@router.patch("/employers/{employer_id}/credits", status_code=200)
async def grant_credits(
    employer_id: UUID = Path(...),
    data: CreditGrantRequest = ...,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Grant credits to an employer and write an audit log entry."""
    service = AdminService(db)
    return await service.grant_employer_credits(
        admin_id=admin_user.id,
        employer_id=employer_id,
        amount=data.amount,
        reason=data.reason,
    )
