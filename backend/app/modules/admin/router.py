"""HTTP endpoints for admin operations."""

from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.modules.auth.service import AuthService
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import User

from .schemas import (
    BulkJobActionRequest,
    BulkUserActionRequest,
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
        admin_id=admin_user.id,
        job_id=job_id,
        action=data.action,
        reason=data.reason
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
