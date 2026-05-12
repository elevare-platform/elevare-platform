from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.modules.users.models import User

router = APIRouter()


@router.post("/register", status_code=201, response_model=AuthResponse)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user account and return tokens.

    Args:
        data: Validated registration payload.
        db: Injected async database session.

    Returns:
        An AuthResponse with user details and JWT access/refresh tokens.

    """
    return await AuthService(db).register_user(data)


@router.post("/login", response_model=AuthResponse, status_code=200)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Authenticate a user by email and password.

    Args:
        data: Validated login credentials.
        db: Injected async database session.

    Returns:
        An AuthResponse with user details and JWT access/refresh tokens.

    """
    return await AuthService(db).login_user(data)


@router.post("/refresh", status_code=200)
async def refresh(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Issue a new access token using a valid refresh token.

    Args:
        data: Payload containing the JWT refresh token.
        db: Injected async database session.

    Returns:
        A dictionary containing the new access token and token type.

    """
    return await AuthService(db).refresh_access_token(data.refresh_token)


@router.post("/logout", status_code=200, response_model=MessageResponse)
async def logout(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MessageResponse:
    """Revoke the refresh token and invalidate the session.

    Args:
        data: Payload containing the refresh token to revoke.
        db: Injected async database session.
        current_user: The authenticated user requesting logout.

    Returns:
        A MessageResponse confirming logout.

    """
    await AuthService(db).revoke_refresh_token(data.refresh_token)
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserResponse, status_code=200)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Retrieve the authenticated user's profile.

    Args:
        current_user: The authenticated user.

    Returns:
        A UserResponse containing the user's profile information.

    """
    return current_user
