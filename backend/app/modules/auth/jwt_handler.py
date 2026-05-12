"""JWT creation and decoding utilities for the Elevare auth system.

Public interface:
- ``create_token_pair`` — generates both access and refresh tokens for a user.
- ``decode_access_token`` — validates an access token and returns a typed payload.

Internal helpers (``_create_access_token``, ``_create_refresh_token``) are
prefixed with ``_`` and should not be called directly outside this module.
"""

import uuid
from datetime import UTC, datetime, timedelta

from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings
from app.core.exceptions import TokenExpiredException, TokenInvalidException
from app.core.schemas import TokenPayload


def _create_access_token(data: dict) -> str:
    payload = data.copy()
    payload.update(
        {
            "exp": datetime.now(UTC)
            + timedelta(minutes=settings.access_token_expire_minutes),
            "type": "access",
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _create_refresh_token(data: dict) -> str:
    payload = data.copy()
    payload.update(
        {
            "exp": datetime.now(UTC)
            + timedelta(days=settings.refresh_token_expire_days),
            "type": "refresh",
            "jti": str(uuid.uuid4()),  # stored in DB — used for revocation lookup
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token.

    Args:
        token: The encoded JWT string from the Authorization header.

    Returns:
        A ``TokenPayload`` with ``sub``, ``role``, and ``type``.

    Raises:
        TokenExpiredException: If the token's ``exp`` claim is in the past.
        TokenInvalidException: If the token is malformed, has a bad signature,
            or is not an access token.

    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except ExpiredSignatureError:
        raise TokenExpiredException() from None
    except JWTError:
        raise TokenInvalidException() from None

    if payload.get("type") != "access":
        raise TokenInvalidException()

    return TokenPayload(
        sub=payload["sub"],
        role=payload["role"],
        type=payload["type"],
    )


def decode_refresh_token(token: str) -> TokenPayload:
    """Decode a refresh token without checking expiry (expiry checked via DB record).

    Args:
        token: The encoded JWT refresh token string.

    Returns:
        A ``TokenPayload`` with ``sub``, ``role``, and ``type``.

    Raises:
        TokenInvalidException: If the token is malformed or has a bad signature.

    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_exp": False},  # expiry is enforced via DB record
        )
    except JWTError:
        raise TokenInvalidException() from None

    if payload.get("type") != "refresh":
        raise TokenInvalidException()

    return TokenPayload(
        sub=payload["sub"],
        role=payload["role"],
        type=payload["type"],
    )


def create_token_pair(user_id: str, role: str) -> dict:
    """Generate an access/refresh token pair for a user.

    Args:
        user_id: The user's UUID as a string — becomes the ``sub`` claim.
        role: The user's role string — embedded in both tokens.

    Returns:
        A dict with ``access_token``, ``refresh_token``, and ``token_type``.

    """
    data = {"sub": str(user_id), "role": role}

    return {
        "access_token": _create_access_token(data),
        "refresh_token": _create_refresh_token(data),
        "token_type": "bearer",
    }
