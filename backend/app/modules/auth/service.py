import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    AccountBannedException,
    AccountDeactivatedException,
    AccountSuspendedException,
    AlreadyExistsException,
    InvalidCredentialsException,
    RefreshTokenMissing,
    RevokedTokenException,
    TokenExpiredException,
    TokenInvalidException,
)
from app.modules.auth.jwt_handler import (
    _create_access_token,
    create_token_pair,
    decode_refresh_token,
)
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.modules.auth.security import hash_password, verify_password
from app.modules.users.enums import AccountStatus
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)

class AuthService:
    """Handles registration, login, token refresh, and logout business logic."""

    def __init__(self, db: AsyncSession):
        self._db = db
        self._user_repo = UserRepository(db)
        self._auth_repo = AuthRepository(db)

    async def register_user(self, data: RegisterRequest, response: Response):
        """Register a new user and return an auth response with token pair.

        Raises:
            AlreadyExistsException: If the email or phone number is already taken.

        """
        logger.info("Registering user...")

        # Check if email already exists
        email = data.email

        user = await self._user_repo.get_user_by_email(email)

        if user:
            raise AlreadyExistsException(message="Email address already exist")

        # Check if phone number already exists
        phone_number = data.phone_number

        user = await self._user_repo.get_user_by_phone(phone_number)

        if user:
            raise AlreadyExistsException(message="Phone number already exist")

        # Hash password and build user data
        # TODO Phase 3.5: change account_status to PENDING_VERIFICATION
        # when email verification endpoint is implemented
        user = await self._user_repo.create_user({
            "first_name": data.first_name,
            "last_name": data.last_name,
            "email": data.email,
            "phone_number": data.phone_number,
            "password_hash": hash_password(data.password),
            "account_status": AccountStatus.ACTIVE.value,
        })

        logger.info(f"User registered successfully with email: {user.email}")

        # TODO: SEND VERIFICATION EMAIL

        token_pair = create_token_pair(user.id, user.role)

        # set cookie
        response.set_cookie(
            key="refresh_token",
            value=token_pair["refresh_token"],
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        )

        # Store refresh token
        await self._auth_repo.create_refresh_token(
            user.id,
            token_pair["refresh_token"],
            datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )

        # Explicitly commit everything
        await self._db.commit()

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                role=user.role,
                account_status=user.account_status
            ),
            access_token=token_pair["access_token"],
            token_type=token_pair["token_type"]
        )

    async def login_user(self, data: LoginRequest, response: Response):
        """Authenticate a user and return an auth response with a fresh token pair.

        Raises:
            InvalidCredentialsException: If the email is unknown or password is wrong.
            AccountSuspendedException: If the account is suspended.
            AccountBannedException: If the account is banned.

        """
        logger.info("Logging in user...")

        user = await self._user_repo.get_user_by_email(data.email)

        if not user or not verify_password(data.password, user.password_hash):
            raise InvalidCredentialsException()

        if user.account_status == AccountStatus.SUSPENDED.value:
            raise AccountSuspendedException()

        if user.account_status == AccountStatus.BANNED.value:
            raise AccountBannedException()

        if user.account_status == AccountStatus.DEACTIVATED.value:
            raise AccountDeactivatedException()

        user.last_login_at = datetime.now(UTC)

        token_pair = create_token_pair(
            user.id,
            user.role
        )

        # set cookie
        response.set_cookie(
            key="refresh_token",
            value=token_pair["refresh_token"],
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        )

        await self._auth_repo.create_refresh_token(
            user.id,
            token_pair["refresh_token"],
            datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )

        # Explicit commit
        await self._db.commit()

        return AuthResponse(
            user=UserResponse(
                id=user.id,
                first_name=user.first_name,
                last_name=user.last_name,
                email=user.email,
                role=user.role,
                account_status=user.account_status,
            ),
            access_token=token_pair["access_token"],
            token_type=token_pair["token_type"],
        )

    async def refresh_access_token(self, token: str) -> dict:
        """Issue a new access token from a valid, non-revoked refresh token.

        Raises:
            TokenInvalidException: If the token is not found or the user no longer exists.
            RevokedTokenException: If the token has already been revoked.
            TokenExpiredException: If the token's expiry has passed.

        """
        if not token:
            raise RefreshTokenMissing()

        token_record = await self._auth_repo.get_refresh_token(token)

        if not token_record:
            raise TokenInvalidException()

        if token_record.is_revoked:
            raise RevokedTokenException()

        if token_record.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise TokenExpiredException()

        payload = decode_refresh_token(token)

        user = await self._user_repo.get_user_by_id(UUID(payload.sub))

        if not user:
            raise TokenInvalidException()

        new_access_token = _create_access_token({
            "sub": payload.sub,
            "role": payload.role,
        })

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
        }


    async def revoke_refresh_token(self, token: str) -> None:
        """Revoke a refresh token, effectively logging the user out.

        Raises:
            TokenInvalidException: If the token is not found.
            RevokedTokenException: If the token was already revoked.

        """
        token_record = await self._auth_repo.get_refresh_token(token)

        if not token_record:
            raise TokenInvalidException()

        if token_record.is_revoked:
            raise RevokedTokenException()

        await self._auth_repo.revoke_refresh_token(token)

        await self._db.commit()

