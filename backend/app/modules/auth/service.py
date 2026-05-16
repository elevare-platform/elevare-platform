"""Business logic for authentication — registration, login, tokens, invites."""

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
    TokenAlreadyUsedException,
    TokenExpiredException,
    TokenInvalidException,
    VerificationTokenExpiredException,
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
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.modules.auth.security import (
    generate_token,
    hash_password,
    hash_token,
    verify_password,
)
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

        # Hash password and build user data — account starts as PENDING_VERIFICATION
        user = await self._user_repo.create_user({
            "first_name": data.first_name,
            "last_name": data.last_name,
            "email": data.email,
            "phone_number": data.phone_number,
            "password_hash": hash_password(data.password),
            "role": data.role.value,
        })

        logger.info(f"User registered successfully with email: {user.email}")

        # Generate verification token — returned in response in stub mode, emailed in production
        verification_token = await self.create_verification_token(user.id)
        if settings.email_stub_mode:
            logger.info(f"Verification token (stub mode): {verification_token}")

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
                account_status=user.account_status,
            ),
            access_token=token_pair["access_token"],
            token_type=token_pair["token_type"],
            verification_token=verification_token if settings.email_stub_mode else None,
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

    async def create_verification_token(self, user_id: UUID) -> str:
        """Generate, hash, and store a new email verification token for the user.

        Invalidates any existing unused tokens before creating the new one.

        Returns:
            The raw (unhashed) token string to include in the verification link.

        """
        raw_token = generate_token()
        hashed_token = hash_token(raw_token)
        await self._auth_repo.create_verification_token(
            user_id,
            hashed_token,
            datetime.now(UTC) + timedelta(hours=settings.email_verification_token_expiry),
        )
        await self._db.commit()
        return raw_token

    async def get_verification_token(self, raw_token: str):
        """Look up and validate a verification token by its raw value."""
        hashed = hash_token(raw_token)
        token_record = await self._auth_repo.get_verification_token(hashed)
        if not token_record:
            raise TokenInvalidException()

        if token_record.is_used:
            raise TokenAlreadyUsedException()

        if token_record.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise VerificationTokenExpiredException()

        return token_record

    async def mark_token_used(self, token) -> None:
        """Mark a verification token as used. Caller is responsible for committing."""
        await self._auth_repo.mark_token_used(token)

    async def verify_email(self, token: str) -> MessageResponse:
        """Verify a user's email using the raw token from the verification link."""
        token_record = await self.get_verification_token(token)

        await self.mark_token_used(token_record)

        user = await self._user_repo.get_user_by_id(token_record.user_id)
        user.account_status = AccountStatus.ACTIVE.value
        user.email_verified = True
        user.email_verified_at = datetime.now(UTC)

        await self._db.commit()

        return MessageResponse(message="Email verified successfully")

    async def create_invite(self, email: str, role: str, admin_id: UUID) -> str:
        """Create an invite token for a new employer account.

        Raises:
            AlreadyExistsException: If a user with that email already exists.

        """
        user = await self._user_repo.get_user_by_email(email)
        if user:
            raise AlreadyExistsException(message="A user with this email already exists")

        raw_token = generate_token()
        hashed_token = hash_token(raw_token)

        await self._auth_repo.create_invite(
            email=email,
            role=role,
            hashed_token=hashed_token,
            expires_at=datetime.now(UTC) + timedelta(days=settings.invite_expiry),
            admin_id=admin_id,
        )

        await self._db.commit()

        if settings.email_stub_mode:
            logger.info(f"Invite token (stub mode): {raw_token}")

        return raw_token

    async def resend_invite(self, token: str, admin_id: UUID) -> str:
        """Invalidate an existing invite and issue a new one.

        Raises:
            TokenInvalidException: If the token does not exist.

        """
        old_invite = await self._auth_repo.get_invite_token(token)
        if not old_invite:
            raise TokenInvalidException()

        await self._auth_repo.revoke_invite_token(old_invite)

        new_raw_token = await self.create_invite(
            email=old_invite.email,
            role=old_invite.role,
            admin_id=admin_id,
        )

        return new_raw_token

    async def accept_invite(self, token: str, data, response) -> AuthResponse:
        """Accept an invite to join the platform.

        Validates the token, registers the user with the invited role and
        ACTIVE status, then returns a full auth response with tokens.

        Raises:
            TokenInvalidException: If the token does not exist.
            VerificationTokenExpiredException: If the token has expired.
            TokenAlreadyUsedException: If the token was already used.

        """
        invite = await self._auth_repo.get_invite_token(token)
        if not invite:
            raise TokenInvalidException()

        if invite.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            raise VerificationTokenExpiredException()

        if invite.is_used:
            raise TokenAlreadyUsedException()

        await self._auth_repo.revoke_invite_token(invite)

        # register user
        logger.info(f"Registering {invite.email} as {invite.role}")

        user = await self._user_repo.create_user({
            "first_name": data.first_name,
            "last_name": data.last_name,
            "email": invite.email,
            "phone_number": data.phone_number,
            "password_hash": hash_password(data.password),
            "role": invite.role,
            "account_status": AccountStatus.ACTIVE.value,
            "email_verified": True,
            "email_verified_at": datetime.now(UTC),
        })

        logger.info("Client successfully registered with invite")

        token_pair = create_token_pair(user.id, invite.role)

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
            token_type=token_pair["token_type"],
        )
