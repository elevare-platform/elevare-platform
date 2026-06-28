import uuid
from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import JobAccessTokens


class AccessTokenRepository:
    def __init__(self, db: AsyncSession):
        self._db = db
    
    async def create(self, token_data: dict) -> JobAccessTokens:
        token = JobAccessTokens(**token_data)
        self._db.add(token)
        await self._db.flush()
        await self._db.refresh(token)
        return token
    
    async def get_all_by_job(self, job_id: uuid.UUID) -> list[JobAccessTokens]:
        result = await self._db.execute(
            select(JobAccessTokens)
            .where(JobAccessTokens.job_id == job_id)
            .order_by(JobAccessTokens.created_at.desc())
        )
        return list(result.scalars().all())
    
    async def get_by_id(self, token_id: uuid.UUID) -> JobAccessTokens | None:
        result = await self._db.execute(
            select(JobAccessTokens).where(JobAccessTokens.id == token_id)
        )
        return result.scalar_one_or_none()
    
    async def revoke(
        self,
        token_id: uuid.UUID,
        revoked_by_id: uuid.UUID,
    ) -> JobAccessTokens | None:
        token = await self.get_by_id(token_id)
        if not token:
            return None
        
        token.is_active = False
        token.revoked_by_id = revoked_by_id
        token.revoked_at = datetime.now(UTC)
        
        await self._db.flush()
        await self._db.refresh(token)
        return token
    
    async def get_valid_by_token(self, token: str) -> JobAccessTokens | None:
        result = await self._db.execute(
            select(JobAccessTokens)
            .where(
                JobAccessTokens.token == token,
                JobAccessTokens.is_active == True,
                JobAccessTokens.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()
