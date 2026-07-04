"""Data-access layer for TalentPoolProfiles."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate_cursor
from app.modules.talent_pool.models import TalentPoolProfiles


class TalentPoolRepository:
    """Handles all database operations for TalentPoolProfiles."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._db = db

    async def create(self, profile_data: dict) -> TalentPoolProfiles:
        """Create a new talent pool profile and return it."""
        profile = TalentPoolProfiles(**profile_data)
        self._db.add(profile)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def get_by_id(
        self,
        profile_id: uuid.UUID,
    ) -> TalentPoolProfiles | None:
        """Fetch a talent pool profile by its primary key, or None if not found."""
        result = await self._db.execute(
            select(TalentPoolProfiles).where(TalentPoolProfiles.id == profile_id)
        )
        return result.scalar_one_or_none()


    async def list(
        self,
        status: str | None = None,
        source: str | None = None,
        job_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 20,
        viewer_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> dict:
        """Return paginated talent pool profiles with optional filters.

        Non-admins only see entries they uploaded or entries added by admins.
        When ``job_id`` is provided, results are ordered by ai_score descending.
        """
        order_by = (
            TalentPoolProfiles.ai_score.desc().nulls_last()
            if job_id
            else TalentPoolProfiles.created_at.desc()
        )

        stmt = select(TalentPoolProfiles).order_by(order_by)

        # Non-admins only see their own uploads OR platform-wide entries (added by admins)
        # Admins see everything
        if not is_admin and viewer_id:
            from sqlalchemy import or_

            from app.modules.users.enums import UserRole
            from app.modules.users.models import User as UserModel
            # Subquery: is the added_by user an admin?
            admin_subq = (
                select(UserModel.id)
                .where(UserModel.id == TalentPoolProfiles.added_by)
                .where(UserModel.role == UserRole.ADMIN.value)
                .correlate(TalentPoolProfiles)
                .exists()
            )
            stmt = stmt.where(
                or_(
                    TalentPoolProfiles.added_by == viewer_id,
                    admin_subq,
                )
            )

        if status:
            stmt = stmt.where(TalentPoolProfiles.status == status)
        if source:
            stmt = stmt.where(TalentPoolProfiles.source == source)
        if job_id:
            stmt = stmt.where(TalentPoolProfiles.sourced_for_job_id == job_id)

        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def update(self, profile_id: uuid.UUID, data: dict) -> TalentPoolProfiles | None:
        """Apply a partial update dict to a profile and return it, or None if not found."""
        profile = await self.get_by_id(profile_id)
        if not profile:
            return None
        for key, value in data.items():
            setattr(profile, key, value)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def list_unscored_for_job(self, job_id: uuid.UUID):
        """Return profiles with a parsed submission that haven't been scored against this job yet.

        Includes profiles already sourced for this job that haven't been scored yet,
        plus pipeline profiles (no job) that can be scored retroactively.
        """
        from sqlalchemy import or_
        stmt = (
            select(TalentPoolProfiles)
            .where(TalentPoolProfiles.parsed_submission_id.is_not(None))
            .where(
                or_(
                    TalentPoolProfiles.sourced_for_job_id == job_id,
                    TalentPoolProfiles.sourced_for_job_id.is_(None),
                )
            )
            .where(TalentPoolProfiles.ai_score.is_(None))
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())
