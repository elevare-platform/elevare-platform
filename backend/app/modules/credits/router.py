"""Employer-facing credits endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.credits.schemas import CreditBalanceResponse
from app.modules.credits.service import CreditsService
from app.modules.users.models import User

router = APIRouter()


@router.get("/balance", response_model=CreditBalanceResponse, status_code=200)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Return the authenticated employer's current credit balance."""
    service = CreditsService(db)
    balance = await service.get_balance(current_user.id)
    return CreditBalanceResponse(balance=balance)
