from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TokenInvalidException
from app.modules.auth.models import RefreshToken
from app.modules.auth.security import hash_token


class AuthRepository:
    """Data-access layer for refresh token persistence."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def create_refresh_token(self, user_id: UUID, raw_token: str, expires_at: datetime):
        """Hash and persist a new refresh token for the given user.

        Returns:
            The newly created RefreshToken ORM instance.

        """
        hashed_token = hash_token(raw_token)

        token = RefreshToken(
            user_id=user_id,
            token=hashed_token,
            expires_at=expires_at
        )
        self._db.add(token)
        await self._db.flush()
        await self._db.refresh(token)

        return token

    async def get_refresh_token(self, raw_token: str):
        """Look up a refresh token record by its raw (unhashed) value.

        Returns:
            The matching RefreshToken, or None if not found.

        """
        hashed_token = hash_token(raw_token)

        stmt = select(RefreshToken).where(RefreshToken.token == hashed_token)
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def revoke_refresh_token(self, raw_token: str):
        """Mark a refresh token as revoked and record the used_at timestamp.

        Raises:
            TokenInvalidException: If the token does not exist.

        """
        token = await self.get_refresh_token(raw_token)
        if token:
            token.is_revoked = True
            token.used_at = datetime.now(UTC)
            return
        raise TokenInvalidException()
