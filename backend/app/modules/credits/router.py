"""Employer-facing credits endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.billing.enums import SubscriptionStatus
from app.modules.billing.repository import BillingRepository
from app.modules.credits.history import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    CreditHistoryService,
)
from app.modules.credits.schemas import CreditBalanceResponse, CreditHistoryPage
from app.modules.credits.service import CreditsService
from app.modules.users.models import User

router = APIRouter()


@router.get("/transactions", response_model=CreditHistoryPage, status_code=200)
async def get_credit_history(
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    cursor: str | None = Query(None, description="next_cursor from the previous page"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """The authenticated employer's organization's credit history, newest first:
    what came in (packs, plan credits, grants, refunds) and what was spent."""
    if current_user.organization_id is None:
        return CreditHistoryPage(items=[], next_cursor=None)
    return await CreditHistoryService(db).get_history(
        current_user.organization_id, limit=limit, cursor=cursor
    )


@router.get("/balance", response_model=CreditBalanceResponse, status_code=200)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Return the authenticated employer's credits: the total, and the part
    included in their plan versus the part they bought."""
    balances = await CreditsService(db).get_balances(current_user.organization_id)
    reset_at = None
    if balances["plan_credits"] > 0:
        subscription = await BillingRepository(db).get_subscription_for_organization(
            current_user.organization_id
        )
        if subscription is not None and subscription.status in (
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.PAST_DUE.value,
        ):
            reset_at = subscription.current_period_end
    return CreditBalanceResponse(
        balance=balances["total"],
        plan_credits=balances["plan_credits"],
        purchased_credits=balances["purchased_credits"],
        plan_credits_reset_at=reset_at,
    )
