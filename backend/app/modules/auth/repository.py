"""Data-access layer for auth tokens — refresh, verification, and invite."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TokenInvalidException
from app.modules.auth.models import EmailVerificationToken, InviteToken, RefreshToken
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

    async def create_verification_token(self, user_id: UUID, hashed_token: str, expires_at: datetime):
        """Invalidate existing unused tokens and create a new email verification token.

        Returns:
            The newly created EmailVerificationToken ORM instance.

        """
        # Invalidate any existing unused tokens for the user
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.is_used.is_(False)
        )
        result = await self._db.execute(stmt)
        existing_tokens = result.scalars().all()

        for t in existing_tokens:
            t.is_used = True
            self._db.add(t)
            await self._db.flush()

        email_verification_token = EmailVerificationToken(
            user_id=user_id,
            token=hashed_token,
            expires_at=expires_at
        )
        self._db.add(email_verification_token)
        await self._db.flush()
        return email_verification_token

    async def get_verification_token(self, token: str):
        """Look up an email verification token by its hashed value.

        Returns:
            The matching EmailVerificationToken, or None if not found.

        """
        stmt = select(EmailVerificationToken).where(
            EmailVerificationToken.token == token,
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def mark_token_used(self, token: EmailVerificationToken) -> None:
        """Mark an email verification token as used so it cannot be reused."""
        token.is_used = True
        self._db.add(token)
        await self._db.flush()

    async def create_invite(
        self,
        email: str,
        role: str,
        hashed_token: str,
        expires_at: datetime,
        admin_id: UUID,
    ) -> InviteToken:
        """Persist a new invite token for the given email and role.

        Returns:
            The newly created InviteToken ORM instance.

        """
        invite = InviteToken(
            email=email,
            token=hashed_token,
            role=role,
            expires_at=expires_at,
            invited_by=admin_id
        )
        self._db.add(invite)
        await self._db.flush()
        await self._db.refresh(invite)
        return invite

    async def get_invite_token(self, token: str) -> InviteToken | None:
        """Look up an invite token by its raw (unhashed) value.

        Returns:
            The matching InviteToken, or None if not found.

        """
        hashed_token = hash_token(token)
        stmt = select(InviteToken).where(InviteToken.token == hashed_token)
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def revoke_invite_token(self, token: InviteToken) -> None:
        """Mark an invite token as used.

        Args:
            token: The InviteToken ORM instance to revoke.

        """
        token.is_used = True
        token.used_at = datetime.now(UTC)
        self._db.add(token)
        await self._db.flush()

