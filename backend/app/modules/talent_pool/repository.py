import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate_cursor
from app.modules.talent_pool.models import TalentPoolProfiles


class TalentPoolRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
    
    async def create(self, profile_data: dict) -> TalentPoolProfiles:
        profile = TalentPoolProfiles(**profile_data)
        self._db.add(profile)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile
    
    async def get_by_id(
        self,
        profile_id: uuid.UUID
    ) -> TalentPoolProfiles | None:
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
    ) -> dict:

        stmt = select(TalentPoolProfiles).order_by(TalentPoolProfiles.created_at.desc())

        if status:
            stmt = stmt.where(TalentPoolProfiles.status == status)
        if source:
            stmt = stmt.where(TalentPoolProfiles.source == source)
        if job_id:
            stmt = stmt.where(TalentPoolProfiles.sourced_for_job_id == job_id)

        return await paginate_cursor(stmt, self._db, cursor, limit)

    async def update(self, profile_id: uuid.UUID, data: dict) -> TalentPoolProfiles | None:
        profile = await self.get_by_id(profile_id)
        if not profile:
            return None
        for key, value in data.items():
            setattr(profile, key, value)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile