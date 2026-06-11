"""FastAPI dependency functions shared across all modules.

Provides:
- ``get_db``: yields an async database session per request.
- ``get_current_user``: extracts and validates the JWT, returns the authenticated User.
- ``require_role``: dependency factory that enforces role-based access control.
"""

import logging
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    AccountBannedException,
    AccountDeactivatedException,
    AccountSuspendedException,
    EmailVerificationRequiredException,
    PermissionDeniedException,
    UserNotFoundException,
)
from app.modules.auth.jwt_handler import decode_access_token
from app.modules.candidates.models import CandidateProfile
from app.modules.users.enums import AccountStatus
from app.modules.users.models import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session for the duration of a request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            raise

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the bearer token and return the authenticated user.

    Enforces account status — raises for PENDING_VERIFICATION, SUSPENDED,
    BANNED, and DEACTIVATED. Use ``get_current_user_any_status`` on endpoints
    that must work regardless of status (e.g. GET /me, resend-verification).

    """
    payload = decode_access_token(token)

    result = await db.execute(
        select(User)
        .options(selectinload(User.employer_profile))
        .where(User.id == payload.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UserNotFoundException()

    # Enforce account status — every protected endpoint inherits this check
    status = user.account_status
    if status == AccountStatus.PENDING_VERIFICATION.value:
        raise EmailVerificationRequiredException()
    if status == AccountStatus.SUSPENDED.value:
        raise AccountSuspendedException()
    if status == AccountStatus.BANNED.value:
        raise AccountBannedException()
    if status == AccountStatus.DEACTIVATED.value:
        raise AccountDeactivatedException()

    return user

async def get_current_user_any_status(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Like get_current_user but skips account status enforcement.

    Use only on endpoints that must be reachable regardless of account status,
    such as GET /me (needed by the frontend to render restricted-account UI)
    and POST /resend-verification-email.

    """
    payload = decode_access_token(token)

    result = await db.execute(
        select(User)
        .options(selectinload(User.employer_profile))
        .where(User.id == payload.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise UserNotFoundException()

    return user

def require_role(*roles: str):
    """Dependency factory that restricts access to users with specific roles.

    Usage::

        @router.get("/admin", dependencies=[Depends(require_role("ADMIN"))])

        # or inject the user at the same time:
        @router.get("/admin")
        async def admin_route(user: User = Depends(require_role("ADMIN", "EMPLOYER"))):
            ...

    Args:
    ----
        *roles: One or more role strings that are permitted to access the route.

    Returns:
    -------
        A FastAPI dependency that returns the current user if their role is
        in the allowed set, or raises ``PermissionDeniedException`` otherwise.

    """
    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedException()
        return current_user

    return _check_role

async def get_candidate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_any_status),
) -> CandidateProfile | None:
    """Return the CandidateProfile for the current user, or None if not found."""
    result = await db.execute(
        select(CandidateProfile)
        .where(CandidateProfile.user_id == current_user.id)
    )
    candidate = result.scalar_one_or_none()

    return candidate

async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield a Redis client and ensure it is closed after the request."""
    redis = aioredis.from_url(settings.redis_url)
    try:
        yield redis
    finally:
        await redis.aclose()


