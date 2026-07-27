"""REST endpoints for the notifications module."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.modules.notifications.repository import NotificationRepository
from app.modules.notifications.schemas import NotificationResponse, UnreadCountResponse
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=dict)
async def list_notifications(
    cursor: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return paginated notifications for the authenticated user."""
    repo = NotificationRepository(db)
    result = await repo.list_for_user(current_user.id, cursor=cursor, limit=limit)
    result["items"] = [NotificationResponse.model_validate(n) for n in result["items"]]
    return result


@router.get("/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the number of unread notifications for the authenticated user."""
    repo = NotificationRepository(db)
    count = await repo.unread_count(current_user.id)
    return UnreadCountResponse(count=count)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a single notification as read."""
    repo = NotificationRepository(db)
    notification = await repo.mark_read(notification_id, current_user.id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    await db.commit()
    return NotificationResponse.model_validate(notification)


@router.patch("/read-all", response_model=dict)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark all unread notifications for the current user as read."""
    repo = NotificationRepository(db)
    count = await repo.mark_all_read(current_user.id)
    await db.commit()
    return {"marked_read": count}
