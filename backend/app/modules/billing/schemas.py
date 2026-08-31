from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.billing.enums import PaymentStatus
from app.modules.billing.models import Payment


class PaymentResponse(BaseModel):
    """Payment details response."""

    model_config = ConfigDict(from_attributes=True)

    organization_id: UUID
    organization_name: str | None = None
    subscription_id: UUID | None = None
    purpose: str
    amount_kobo: int
    currency: str
    status: PaymentStatus
    provider: str
    provider_reference: str | None = None
    credits_granted: int | None = None
    initiated_by_user_id: UUID | None = None
    failure_reason: str | None = None
    paid_at: datetime | None = None
    checkout_url: str | None = None
    checkout_url_expires_at: datetime | None = None

    @classmethod
    def from_orm(cls, payment: Payment) -> "PaymentResponse":
        return cls(
            organization_id=payment.organization_id,
            organization_name=payment.organization.company_name
            if payment.organization.company_name
            else None,
            subscription_id=payment.subscription_id,
            purpose=payment.purpose,
            amount_kobo=payment.amount_kobo,
            currency=payment.currency,
            status=payment.status,
            provider=payment.provider,
            provider_reference=payment.provider_reference,
            credits_granted=payment.credits_granted,
            initiated_by_user_id=payment.initiated_by_user_id,
            failure_reason=payment.failure_reason,
            paid_at=payment.paid_at,
            checkout_url=payment.checkout_url,
            checkout_url_expires_at=payment.checkout_url_expires_at,
        )


class CreditPackageSchema(BaseModel):
    """Credit package details response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    credits: int
    price_kobo: int
    currency: str
    is_active: bool
    sort_order: int


class PlanResponse(BaseModel):
    """Subscription plan catalog entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None = None
    price_kobo: int
    currency: str
    interval: str
    job_posting_limit: int | None = None
    included_credits: int | None = None
    is_active: bool
    sort_order: int


class CurrentSubscriptionResponse(BaseModel):
    """What plan the caller's organization is actually on right now.

    Starter has no Subscription row (null subscription = free tier, per
    BillingService.get_effective_plan) — status/dates are null in that case,
    the frontend just shows the plan with no renewal date.
    """

    plan: PlanResponse
    status: str | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class CreditCheckoutRequest(BaseModel):
    """Request body for POST /billing/credits/checkout."""

    credit_package_code: str


class CheckoutResponse(BaseModel):
    """Response for an endpoint that always redirects to a real checkout."""

    checkout_url: str


class SubscriptionCheckoutRequest(BaseModel):
    """Request body for POST /billing/subscription/checkout."""

    plan_code: str


class SubscriptionCheckoutResponse(BaseModel):
    """Response for subscription checkout — three shapes:

    - Paid plan: `checkout_url` set, `activated=False`.
    - Free plan, nothing to protect: `checkout_url=None`, `activated=True`
      — switched immediately.
    - Free plan, but an active paid subscription exists: `checkout_url=None`,
      `activated=False`, `effective_at` set — the downgrade is scheduled for
      period end rather than applied now, so already-paid time isn't lost.
    """

    checkout_url: str | None
    activated: bool
    effective_at: datetime | None = None
