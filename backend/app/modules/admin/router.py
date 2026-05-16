"""HTTP endpoints for admin operations."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.modules.auth.service import AuthService
from app.modules.users.models import User

from .schemas import InviteRequest

router = APIRouter()


@router.post("/employers/invite", status_code=200)
async def create_invite(
    data: InviteRequest,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_role("ADMIN")),
):
    """Create an employer invite. Returns the raw token in stub mode.

    Args:
        data: Invite payload containing the target email and role.
        db: Injected async database session.
        admin_user: The authenticated ADMIN user.

    Returns:
        The invite token in stub mode, or a success message in production.

    """
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
    """Invalidate an existing invite and issue a new one.

    Args:
        token: The raw invite token to invalidate.
        db: Injected async database session.
        admin_user: The authenticated ADMIN user.

    Returns:
        The new invite token in stub mode, or a success message in production.

    """
    service = AuthService(db)
    raw_token = await service.resend_invite(token, admin_user.id)
    if settings.email_stub_mode:
        return {"invite_token": raw_token}
    return SuccessResponse(message="Invite resent")
