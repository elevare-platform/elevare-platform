"""Employer-facing credits endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.modules.billing.enums import SubscriptionStatus
from app.modules.billing.repository import BillingRepository
from app.modules.credits.schemas import CreditBalanceResponse
from app.modules.credits.service import CreditsService
from app.modules.users.models import User

router = APIRouter()


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
