"""SQLAlchemy ORM models for the billing module — plans, subscriptions,
payments, and the inbound webhook log.

Two primitives, kept deliberately separate (see
docs/subscription-payment-architecture-review.md §5.1): `Subscription`
gates capacity (job posting count), `EmployerCredits` (existing, in
`credits/models.py`) is a consumable wallet. Both are funded through
`Payment`, distinguished by `purpose`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.billing.enums import PaymentStatus

if TYPE_CHECKING:
    from app.modules.users.models import Organization, User


class Plan(BaseModel):
    """Catalog of subscription tiers. Admin-managed, rarely written."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("price_kobo >= 0", name="ck_plans_price_non_negative"),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NGN", server_default="NGN"
    )
    interval: Mapped[str] = mapped_column(String(10), nullable=False)
    job_posting_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    included_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # The Paystack Plan this maps to — null until set up on Paystack's side
    # (dashboard or a one-off script with live credentials). Checkout for a
    # paid plan with no provider_plan_code still works as a one-off charge,
    # it just won't auto-renew — see BillingService.start_subscription_checkout.
    provider_plan_code: Mapped[str | None] = mapped_column(String(255), nullable=True)

    subscriptions: Mapped[list[Subscription]] = relationship(
        "Subscription", back_populates="plan"
    )


class CreditPackage(BaseModel):
    """A purchasable bundle of credits — e.g. '50 credits for ₦65,000'.

    Deliberately separate from `Plan`: a plan is a recurring subscription
    tier with fields like `interval`/`job_posting_limit` that don't apply
    to a one-off credit purchase. Both `credits` and `price_kobo` live on
    this one row so a checkout only ever needs a `code` — never a
    caller-supplied amount or quantity to trust.
    """

    __tablename__ = "credit_packages"
    __table_args__ = (
        CheckConstraint(
            "price_kobo >= 0", name="ck_credit_packages_price_non_negative"
        ),
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    price_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NGN", server_default="NGN"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class Subscription(BaseModel):
    """One row per organization's current subscription state.

    Renewals update this same row's `current_period_end` rather than
    inserting a new row — history lives in `payments`, not here.
    """

    __tablename__ = "subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_subscription_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    # Set together from the Paystack `subscription.create` webhook.
    # provider_subscription_id holds their subscription_code; cancelling
    # via POST /subscription/disable needs both that code AND this
    # separate email_token — Paystack, not us, requires two different
    # values here.
    provider_customer_code: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    provider_email_token: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    current_period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    current_period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    canceled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="subscription"
    )
    plan: Mapped[Plan] = relationship("Plan", back_populates="subscriptions")
    payments: Mapped[list[Payment]] = relationship(
        "Payment", back_populates="subscription"
    )


class Payment(BaseModel):
    """Append-only history of every charge attempt — subscription renewals
    and one-off credit top-ups both flow through this single table.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_kobo >= 0", name="ck_payments_amount_non_negative"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="NGN", server_default="NGN"
    )
    status: Mapped[PaymentStatus] = mapped_column(
        String(20),
        default=PaymentStatus.PENDING.value,
        nullable=False,
        server_default=PaymentStatus.PENDING.value,
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_reference: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    credits_granted: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Paystack's stable per-customer identifier, captured off a verified
    # transaction (TransactionResult.provider_customer_code). This is how
    # the subscription.create webhook — which carries none of our own
    # metadata — gets correlated back to an organization.
    provider_customer_code: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    # Which Plan this payment is meant to activate, for SUBSCRIPTION_INITIAL/
    # RENEWAL purposes — same reasoning as credits_granted: decide what this
    # payment is for at checkout time, read it back at finalize time, never
    # re-derive it from the amount charged.
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkout_url_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="payments"
    )
    subscription: Mapped[Subscription | None] = relationship(
        "Subscription", back_populates="payments"
    )
    plan: Mapped[Plan | None] = relationship("Plan")
    initiated_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[initiated_by_user_id]
    )


class WebhookEvent(BaseModel):
    """Raw inbound webhook log — the idempotency gate for payment webhooks.

    `(provider, provider_event_id)` is the dedup key: the handler inserts
    this row first, inside the same transaction as any resulting credit
    grant or subscription activation; a unique-constraint violation means
    "already processed," short-circuit without reprocessing.
    """

    __tablename__ = "webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id", name="uq_webhook_events_provider_event"
        ),
    )

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
