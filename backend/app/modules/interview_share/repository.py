"""Data access for interview share links."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.interview_share.models import InterviewShareLink
from app.modules.jobs.models import Job


class InterviewShareRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def lock_job(self, job_id: uuid.UUID) -> None:
        """Hold the job's row until the transaction ends, so two people creating a link
        for the same job at once take turns instead of racing."""
        await self._db.execute(select(Job.id).where(Job.id == job_id).with_for_update())

    async def get_active_for_job(self, job_id: uuid.UUID) -> InterviewShareLink | None:
        """The job's link that has not been revoked (it may have expired)."""
        result = await self._db.execute(
            select(InterviewShareLink).where(
                InterviewShareLink.job_id == job_id,
                InterviewShareLink.revoked_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_active(self, job_id: uuid.UUID, now: datetime) -> bool:
        """Revoke the job's current link. Returns whether there was one."""
        result = await self._db.execute(
            update(InterviewShareLink)
            .where(
                InterviewShareLink.job_id == job_id,
                InterviewShareLink.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        return result.rowcount > 0

    async def create(
        self,
        *,
        job_id: uuid.UUID,
        token: str,
        created_by: uuid.UUID,
        expires_at: datetime,
    ) -> InterviewShareLink:
        link = InterviewShareLink(
            job_id=job_id, token=token, created_by=created_by, expires_at=expires_at
        )
        self._db.add(link)
        await self._db.flush()
        return link

    async def get_by_token(self, token: str) -> InterviewShareLink | None:
        result = await self._db.execute(
            select(InterviewShareLink).where(InterviewShareLink.token == token)
        )
        return result.scalar_one_or_none()

    async def record_view(self, link_id: uuid.UUID, now: datetime) -> None:
        """Count one opening of the link (an atomic increment, safe when two people
        open it at the same moment)."""
        await self._db.execute(
            update(InterviewShareLink)
            .where(InterviewShareLink.id == link_id)
            .values(
                view_count=InterviewShareLink.view_count + 1, last_viewed_at=now
            )
        )
