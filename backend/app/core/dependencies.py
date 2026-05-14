"""FastAPI dependency functions shared across all modules.

Provides:
- ``get_db``: yields an async database session per request.
- ``get_current_user``: extracts and validates the JWT, returns the authenticated User.
- ``require_role``: dependency factory that enforces role-based access control.
"""

import logging
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.exceptions import (
    AccountBannedException,
    AccountDeactivatedException,
    AccountSetupIncompleteException,
    AccountSuspendedException,
    EmailVerificationRequiredException,
    PermissionDeniedException,
    UserNotFoundException,
)
from app.modules.auth.jwt_handler import decode_access_token
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

    Args:
        token: JWT extracted from the ``Authorization: Bearer`` header.
        db: Injected database session.

    Returns:
        The ``User`` ORM instance for the authenticated user.

    Raises:
        TokenExpiredException: If the token has expired.
        TokenInvalidException: If the token is malformed or has a bad signature.
        UserNotFoundException: If the user ID in the token no longer exists in the DB.

    """
    payload = decode_access_token(token)  # raises TokenExpiredException / TokenInvalidException

    result = await db.execute(select(User).where(User.id == payload.sub))
    user = result.scalar_one_or_none()

    if user is None:
        raise UserNotFoundException()

    # Enforce account status — every protected endpoint inherits this check
    status = user.account_status
    if status == AccountStatus.PENDING_VERIFICATION.value:
        raise EmailVerificationRequiredException()
    if status == AccountStatus.INVITED.value:
        raise AccountSetupIncompleteException()
    if status == AccountStatus.SUSPENDED.value:
        raise AccountSuspendedException()
    if status == AccountStatus.BANNED.value:
        raise AccountBannedException()
    if status == AccountStatus.DEACTIVATED.value:
        raise AccountDeactivatedException()

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
        *roles: One or more role strings that are permitted to access the route.

    Returns:
        A FastAPI dependency that returns the current user if their role is
        in the allowed set, or raises ``PermissionDeniedException`` otherwise.

    """
    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedException()
        return current_user

    return _check_role
