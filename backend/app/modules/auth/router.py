"""HTTP endpoints for the auth module."""

import logging

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    get_current_user_allowing_password_change,
    get_current_user_any_status,
    get_db,
    oauth2_scheme,
)
from app.core.exceptions import RefreshTokenMissing
from app.core.limiter import limiter
from app.modules.auth.jwt_handler import decode_access_token
from app.modules.auth.schemas import (
    AcceptInviteRequest,
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", status_code=201, response_model=AuthResponse)
@limiter.limit("10/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user account and return tokens."""
    return await AuthService(db).register_user(data, response)


@router.post("/login", response_model=AuthResponse, status_code=200)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate a user by email and password."""
    return await AuthService(db).login_user(data, response)


@router.post("/refresh", status_code=200)
async def refresh(
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Issue a new access token using a valid refresh token."""
    if refresh_token is None:
        raise RefreshTokenMissing()
    return await AuthService(db).refresh_access_token(refresh_token)


@router.post("/logout", status_code=200, response_model=MessageResponse)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_allowing_password_change),
) -> MessageResponse:
    """Revoke the refresh token and invalidate the session.

    Also open to an account that still has to change its temporary password, so
    it can sign out.
    """
    if refresh_token is None:
        raise RefreshTokenMissing()
    await AuthService(db).revoke_refresh_token(refresh_token)
    response.delete_cookie(key="refresh_token")
    return MessageResponse(message="Successfully logged out")


@router.post("/change-password", response_model=AuthResponse, status_code=200)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_allowing_password_change),
) -> AuthResponse:
    """Choose a new password. Open to any logged-in user, and the only request
    (besides logout) an account with a temporary password may make until done."""
    return await AuthService(db).change_password(current_user, data, response)


@router.get("/me", response_model=UserResponse, status_code=200)
async def get_me(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user_any_status),
) -> UserResponse:
    """Retrieve the authenticated user's profile.

    ``must_change_password`` is read from the token, so a page reload still knows
    the user has to choose a new password.
    """
    return AuthService._build_user_response(
        current_user,
        must_change_password=decode_access_token(token).must_change_password,
    )


@router.post("/verify-email", status_code=200, response_model=MessageResponse)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    token: str,
    role: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """Verify a user's email address using a token.

    ``role`` is optional and lets the "I signed up as the wrong type of user"
    link in the verification email correct CANDIDATE/EMPLOYER in the same click.
    """
    return await AuthService(db).verify_email(token, switch_role=role)


@router.post(
    "/resend-verification-email", status_code=200, response_model=MessageResponse
)
@limiter.limit("3/minute")
async def resend_verification_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_any_status),
) -> MessageResponse:
    """Resend an email verification token to the authenticated user."""
    raw_token = await AuthService(db).create_verification_token(current_user.id)
    if settings.email_stub_mode:
        return MessageResponse(message=f"Verification token (stub): {raw_token}")
    return MessageResponse(message="Verification email sent")


@router.post("/invite/accept", status_code=200, response_model=AuthResponse)
@limiter.limit("10/minute")
async def accept_invite(
    request: Request,
    token: str,
    data: AcceptInviteRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Accept an invite to join the platform."""
    return await AuthService(db).accept_invite(token, data, response)
