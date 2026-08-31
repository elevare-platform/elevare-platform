"""Data-access layer for Notification records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate_cursor
from app.modules.notifications.models import Notification


class NotificationRepository:
    """CRUD operations for :class:`Notification`."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        recipient_id: uuid.UUID,
        type: str,
        title: str,
        body: str | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        context: dict | None = None,
    ) -> Notification:
        """Insert a new notification and return it."""
        notification = Notification(
            recipient_id=recipient_id,
            type=type,
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
        )
        self._db.add(notification)
        await self._db.flush()
        await self._db.refresh(notification)
        return notification

    async def list_for_user(
        self,
        recipient_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated notifications for a user, newest first."""
        stmt = (
            select(Notification)
            .where(Notification.recipient_id == recipient_id)
            .order_by(Notification.created_at.desc())
        )
        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def unread_count(self, recipient_id: uuid.UUID) -> int:
        """Return the number of unread notifications for a user."""
        result = await self._db.scalar(
            select(func.count()).where(
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
        )
        return result or 0

    async def mark_read(
        self, notification_id: uuid.UUID, recipient_id: uuid.UUID
    ) -> Notification | None:
        """Mark a single notification read; returns None if not found or not owned."""
        result = await self._db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_id == recipient_id,
            )
        )
        notification = result.scalar_one_or_none()
        if not notification:
            return None
        if not notification.read_at:
            notification.read_at = datetime.now(UTC)
            await self._db.flush()
        return notification

    async def mark_all_read(self, recipient_id: uuid.UUID) -> int:
        """Mark all unread notifications for a user as read. Returns count updated."""
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        return result.rowcount
