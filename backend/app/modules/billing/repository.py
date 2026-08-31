"""Data-access layer for plans, subscriptions, payments, and webhook events.

No business logic here — that's `BillingService`, added in Phase 2 once
checkout/webhook handling lands. Phase 1 only needs enough to seed and
read the plan catalog and to give Phase 2 a stable base to build on.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.billing.models import (
    CreditPackage,
    Payment,
    Plan,
    Subscription,
    WebhookEvent,
)


class BillingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # --- Plans ---

    async def list_active_plans(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_plan_by_code(self, code: str) -> Plan | None:
        stmt = select(Plan).where(Plan.code == code)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_plan_by_id(self, plan_id: uuid.UUID | None) -> Plan | None:
        if plan_id is None:
            return None
        stmt = select(Plan).where(Plan.id == plan_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    # --- Subscriptions ---

    async def get_subscription_for_organization(
        self, organization_id: uuid.UUID
    ) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.organization_id == organization_id
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_subscription(self, data: dict) -> Subscription:
        subscription = Subscription(**data)
        self._db.add(subscription)
        await self._db.flush()
        return subscription

    async def update_subscription(
        self, subscription_id: uuid.UUID, data: dict
    ) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.id == subscription_id)
        result = await self._db.execute(stmt)
        subscription = result.scalar_one_or_none()
        if subscription is None:
            return None
        for key, value in data.items():
            setattr(subscription, key, value)
        await self._db.flush()
        return subscription

    async def get_recent_webhook_event_by_customer_code(
        self, provider: str, event_type: str, customer_code: str
    ) -> WebhookEvent | None:
        """Find a recent webhook event of this type whose payload's
        `data.customer.customer_code` matches — used to catch up a
        `subscription.create` that arrived before the `charge.success` it
        depends on for correlation (Paystack doesn't guarantee delivery
        order between the two, confirmed in production: subscription.create
        landed first for a real test-mode subscribe). Scans in Python
        rather than a JSONB path query — event volume here is low enough
        that correctness-first is fine.
        """
        stmt = (
            select(WebhookEvent)
            .where(WebhookEvent.provider == provider, WebhookEvent.event_type == event_type)
            .order_by(WebhookEvent.created_at.desc())
            .limit(50)
        )
        result = await self._db.execute(stmt)
        for event in result.scalars().all():
            data = event.payload.get("data", {})
            if (data.get("customer") or {}).get("customer_code") == customer_code:
                return event
        return None

    async def get_subscription_by_provider_customer_code(
        self, provider_customer_code: str
    ) -> Subscription | None:
        stmt = select(Subscription).where(
            Subscription.provider_customer_code == provider_customer_code
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_succeeded_payment_by_customer_code(
        self, provider_customer_code: str
    ) -> Payment | None:
        """The most recent successful subscription payment for a Paystack
        customer — used to correlate the `subscription.create` webhook
        (which carries none of our own metadata) back to an organization.
        """
        stmt = (
            select(Payment)
            .where(
                Payment.provider_customer_code == provider_customer_code,
                Payment.purpose.in_(["SUBSCRIPTION_INITIAL", "SUBSCRIPTION_RENEWAL"]),
                Payment.status == "SUCCEEDED",
            )
            .order_by(Payment.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def list_lapsed_cancellations(self, older_than: datetime) -> list[Subscription]:
        """ACTIVE subscriptions scheduled to cancel whose period has already
        ended — candidates for the expiry sweep (see billing/tasks.py).
        """
        stmt = select(Subscription).where(
            Subscription.status == "ACTIVE",
            Subscription.cancel_at_period_end.is_(True),
            Subscription.current_period_end < older_than,
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_lapsed_past_due(self, older_than: datetime) -> list[Subscription]:
        """PAST_DUE subscriptions (a renewal charge failed) whose grace
        period — current_period_end — has passed without a successful
        retry. Candidates for the expiry sweep, same as an explicit cancel.
        """
        stmt = select(Subscription).where(
            Subscription.status == "PAST_DUE",
            Subscription.current_period_end < older_than,
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # --- Payments ---

    async def create_payment(self, data: dict) -> Payment:
        payment = Payment(**data)
        self._db.add(payment)
        await self._db.flush()
        return payment

    async def update_payment(self, payment_id: uuid.UUID, data: dict) -> Payment | None:
        payment = await self.get_payment_by_id(payment_id)
        if payment is None:
            return None

        for key, value in data.items():
            setattr(payment, key, value)
        await self._db.flush()
        return payment

    async def get_payment_by_id(self, payment_id: uuid.UUID) -> Payment | None:
        stmt = select(Payment).where(Payment.id == payment_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_payment_by_reference(self, provider_reference: str) -> Payment | None:
        stmt = select(Payment).where(Payment.provider_reference == provider_reference)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_pending_payment(
        self, organization_id: uuid.UUID, purpose: str
    ) -> Payment | None:
        """Find an in-flight checkout to avoid creating a duplicate on double-click.

        Deliberately does not filter by reference — the whole point of this
        lookup is to run *before* a reference is minted, so the caller can
        decide whether to reuse an existing PENDING payment or create a new
        one.
        """
        stmt = select(Payment).where(
            Payment.organization_id == organization_id,
            Payment.purpose == purpose,
            Payment.status == "PENDING",
        )
        result = await self._db.execute(stmt)
        return result.scalars().first()

    async def list_payments_for_organization(
        self, organization_id: uuid.UUID
    ) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.organization_id == organization_id)
            .options(selectinload(Payment.organization))
            .order_by(Payment.created_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_stale_pending_payments(self, older_than: datetime) -> list[Payment]:
        """Payments still PENDING past `older_than` — candidates for the
        reconciliation sweep (see billing/tasks.py).
        """
        stmt = select(Payment).where(
            Payment.status == "PENDING",
            Payment.created_at < older_than,
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # --- Webhook events (idempotency gate, see billing/models.py:WebhookEvent) ---

    async def record_webhook_event(
        self,
        *,
        provider: str,
        provider_event_id: str,
        event_type: str,
        payload: dict,
    ) -> WebhookEvent:
        """Insert the dedup row. Caller must catch IntegrityError on the
        (provider, provider_event_id) unique constraint to detect a replay.
        """
        event = WebhookEvent(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
        )
        self._db.add(event)
        await self._db.flush()
        return event

    async def get_webhook_event_by_id(self, event_id: uuid.UUID) -> WebhookEvent | None:
        stmt = select(WebhookEvent).where(WebhookEvent.id == event_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    # --- Credit packages ---
    async def list_active_credit_packages(self) -> list[CreditPackage]:
        stmt = (
            select(CreditPackage)
            .where(CreditPackage.is_active.is_(True))
            .order_by(CreditPackage.sort_order)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_credit_package_by_id(
        self, package_id: uuid.UUID
    ) -> CreditPackage | None:
        stmt = select(CreditPackage).where(CreditPackage.id == package_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_credit_package_by_code(self, code: str) -> CreditPackage | None:
        stmt = select(CreditPackage).where(CreditPackage.code == code)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()
