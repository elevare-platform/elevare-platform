"""Data-access layer for MatchNotification records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.models import MatchNotification


class MatchNotificationRepository:
    """CRUD operations for :class:`MatchNotification`."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_new_profile_ids_for_job(self, job_id: uuid.UUID) -> set[uuid.UUID]:
        """Return talent_pool_profile_ids that are still marked is_new for a job."""
        result = await self._db.execute(
            select(MatchNotification.talent_pool_profile_id).where(
                MatchNotification.job_id == job_id,
                MatchNotification.is_new.is_(True),
                MatchNotification.talent_pool_profile_id.is_not(None),
            )
        )
        return {row[0] for row in result.all()}

    async def count_new_for_job(self, job_id: uuid.UUID) -> int:
        """Return the number of new (unseen) matches for a job."""
        from sqlalchemy import func

        result = await self._db.scalar(
            select(func.count()).where(
                MatchNotification.job_id == job_id,
                MatchNotification.is_new.is_(True),
            )
        )
        return result or 0

    async def mark_job_matches_viewed(self, job_id: uuid.UUID) -> None:
        """Flip is_new=False and set viewed_at for all new matches on a job."""
        await self._db.execute(
            update(MatchNotification)
            .where(
                MatchNotification.job_id == job_id,
                MatchNotification.is_new.is_(True),
            )
            .values(is_new=False, viewed_at=datetime.now(UTC))
        )
        await self._db.flush()
