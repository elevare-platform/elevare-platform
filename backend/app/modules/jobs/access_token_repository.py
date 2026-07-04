"""Data-access layer for JobAccessTokens."""
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.jobs.models import JobAccessTokens


class AccessTokenRepository:
    """Handles all database operations for JobAccessTokens."""

    def __init__(self, db: AsyncSession):
        """Initialise with an async database session."""
        self._db = db

    async def create(self, token_data: dict) -> JobAccessTokens:
        """Create a new access token record and return it."""
        token = JobAccessTokens(**token_data)
        self._db.add(token)
        await self._db.flush()
        await self._db.refresh(token)
        return token

    async def get_all_by_job(self, job_id: uuid.UUID) -> list[JobAccessTokens]:
        """Return all access tokens for a job, ordered by most recent first."""
        result = await self._db.execute(
            select(JobAccessTokens)
            .where(JobAccessTokens.job_id == job_id)
            .order_by(JobAccessTokens.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, token_id: uuid.UUID) -> JobAccessTokens | None:
        """Fetch an access token by its primary key, or None if not found."""
        result = await self._db.execute(
            select(JobAccessTokens).where(JobAccessTokens.id == token_id)
        )
        return result.scalar_one_or_none()

    async def revoke(
        self,
        token_id: uuid.UUID,
        revoked_by_id: uuid.UUID,
    ) -> JobAccessTokens | None:
        """Mark a token as inactive and record who revoked it and when."""
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
        """Return an active, non-expired token by its string value, or None."""
        result = await self._db.execute(
            select(JobAccessTokens)
            .where(
                JobAccessTokens.token == token,
                JobAccessTokens.is_active.is_(True),
                JobAccessTokens.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()
