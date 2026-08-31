from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_org_role, require_role
from app.modules.billing.repository import BillingRepository
from app.modules.billing.schemas import (
    CheckoutResponse,
    CreditCheckoutRequest,
    CreditPackageSchema,
    CurrentSubscriptionResponse,
    PaymentResponse,
    PlanResponse,
    SubscriptionCheckoutRequest,
    SubscriptionCheckoutResponse,
)
from app.modules.billing.service import BillingService
from app.modules.users.models import User

webhook_router = APIRouter()
public_router = APIRouter()
router = APIRouter()


@webhook_router.post("/webhooks/{provider_name}", status_code=200)
async def receive_webhook(
    provider_name: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()

    service = BillingService(db)

    await service.handle_webhook(
        provider=provider_name, raw_body=raw_body, headers=dict(request.headers)
    )

    return {"status": "ok"}


@public_router.get("/plans", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)):
    """Active subscription plans — powers the pricing page."""
    repo = BillingRepository(db)
    return await repo.list_active_plans()


@public_router.get("/credit-packages", response_model=list[CreditPackageSchema])
async def list_credit_packages(db: AsyncSession = Depends(get_db)):
    """Purchasable credit bundles."""
    repo = BillingRepository(db)
    return await repo.list_active_credit_packages()


@router.get("/subscription", response_model=CurrentSubscriptionResponse)
async def get_current_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """What plan the caller's organization is on right now, and renewal
    details if it's an active paid subscription. Any member can view —
    same transparency rationale as /payments.
    """
    service = BillingService(db)
    result = await service.get_current_subscription(current_user.organization_id)
    return CurrentSubscriptionResponse(**result)


@router.post("/subscription/cancel", response_model=CurrentSubscriptionResponse)
async def cancel_subscription(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_org_role("OWNER", "ADMIN")),
):
    """Cancel the organization's paid subscription at period end. OWNER/ADMIN
    only — same reasoning as starting a checkout, this changes what the
    organization is billed. Access continues until the current period ends.
    """
    service = BillingService(db)
    await service.cancel_subscription(current_user.organization_id)
    await db.commit()
    result = await service.get_current_subscription(current_user.organization_id)
    return CurrentSubscriptionResponse(**result)


@router.post("/credits/checkout", response_model=CheckoutResponse)
async def start_credit_checkout(
    data: CreditCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_org_role("OWNER", "ADMIN")),
):
    """Start a checkout for a one-off credit top-up. OWNER/ADMIN only —
    this spends the organization's money.
    """
    service = BillingService(db)
    checkout_url = await service.start_credit_topup_checkout(
        organization_id=current_user.organization_id,
        credit_package_code=data.credit_package_code,
        customer_email=current_user.email,
        initiated_by_user_id=current_user.id,
    )
    return CheckoutResponse(checkout_url=checkout_url)


@router.post("/subscription/checkout", response_model=SubscriptionCheckoutResponse)
async def start_subscription_checkout(
    data: SubscriptionCheckoutRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_org_role("OWNER", "ADMIN")),
):
    """Start a subscription checkout, or activate immediately for a free
    plan. OWNER/ADMIN only — this changes what the organization is billed.
    """
    service = BillingService(db)
    result = await service.start_subscription_checkout(
        organization_id=current_user.organization_id,
        plan_code=data.plan_code,
        customer_email=current_user.email,
        initiated_by_user_id=current_user.id,
    )
    return SubscriptionCheckoutResponse(
        checkout_url=result.checkout_url,
        activated=result.activated,
        effective_at=result.effective_at,
    )


@router.get("/payments", response_model=list[PaymentResponse])
async def list_payments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Billing/payment history for the caller's organization. Any member —
    transparency across the team, not just the owner.
    """
    if not current_user.organization_id:
        return []
    repo = BillingRepository(db)
    payments = await repo.list_payments_for_organization(current_user.organization_id)
    return [PaymentResponse.from_orm(p) for p in payments]


@router.get("/checkout/{reference}/verify", response_model=PaymentResponse)
async def verify_checkout(
    reference: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("EMPLOYER")),
):
    """Called by the frontend right after the customer is redirected back
    from Paystack, to confirm status without waiting on the webhook.
    """
    service = BillingService(db)
    payment = await service.verify_checkout(
        reference, requesting_organization_id=current_user.organization_id
    )
    return PaymentResponse.from_orm(payment)
