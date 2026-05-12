import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db

from .schemas import RegisterRequest, UserResponse
from .service import UserService

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/register", status_code=201, response_model=UserResponse)
async def register_user(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    user_service = UserService(db)
    return await user_service.register(data)
