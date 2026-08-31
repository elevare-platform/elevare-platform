"""
Billing Service
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import get_email_service
from app.core.exceptions import (
    CreditPackageNotFoundException,
    InvalidWebhookSignatureException,
    JobPostingLimitExceededException,
    NoActiveSubscriptionException,
    NotFoundException,
    PaymentVerificationException,
    PaystackVerificationError,
    PermissionDeniedException,
    PlanNotFoundException,
    PlanUpgradeRequiredException,
)
from app.modules.billing.enums import PaymentStatus, SubscriptionStatus
from app.modules.billing.models import Payment, Plan, Subscription, WebhookEvent
from app.modules.billing.providers.base import ParsedWebhookEvent, TransactionResult
from app.modules.credits.service import CreditsService
from app.modules.employer.repository import EmployerRepository
from app.modules.jobs.models import Job
from app.modules.notifications.repository import NotificationRepository
from app.modules.users.models import User

from .providers.paystack import PaystackAdapter
from .repository import BillingRepository

_CHECKOUT_URL_TTL = timedelta(minutes=30)
_WEBHOOK_SIGNATURE_HEADERS = {"paystack": "x-paystack-signature"}

logger = logging.getLogger(__name__)


@dataclass
class SubscriptionCheckoutResult:
    """Outcome of `start_subscription_checkout` — three distinct shapes:

    - Paid plan: `checkout_url` set, `activated=False`, `effective_at=None`
      — redirect the customer, nothing changes until they pay.
    - Free plan, nothing paid to protect: `checkout_url=None`,
      `activated=True`, `effective_at=None` — switched immediately.
    - Free plan, but an active paid subscription exists: `checkout_url=None`,
      `activated=False`, `effective_at=<current_period_end>` — the org kept
      what it already paid for; the switch to the free plan is scheduled
      for period end (via `cancel_subscription`) rather than applied now.
    """

    checkout_url: str | None
    activated: bool
    effective_at: datetime | None = None


class BillingService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._repo = BillingRepository(db)
        self._adapter = PaystackAdapter(settings.paystack_secret_key)
        self._employer_repo = EmployerRepository(db)

    async def get_effective_plan(self, organization_id: uuid.UUID) -> Plan:
        """The plan an organization is actually on right now.

        No Subscription row, or one that isn't ACTIVE, means implicitly on
        Starter — matches the architecture review's "null subscription =
        free tier" convention. Every plan-gate in the codebase should read
        this, not query Subscription directly, so "what plan is this org
        on" is answered in exactly one place — which is also why disabling
        gating for testing only needs to happen here, not at every call site.
        """
        if not settings.plan_gates_enabled:
            # Testing/staging escape hatch — every org resolves to the top
            # plan, so every gate that reads this passes. Toggle via the
            # PLAN_GATES_ENABLED env var; must stay True in production.
            unlocked = await self._repo.get_plan_by_code("professional")
            if unlocked is not None:
                return unlocked

        subscription = await self._repo.get_subscription_for_organization(
            organization_id
        )
        if subscription is not None and subscription.status in (
            SubscriptionStatus.ACTIVE.value,
            # A failed renewal charge doesn't cut access immediately — the
            # org keeps its plan through a grace period (until
            # current_period_end) so a transient card decline doesn't
            # instantly downgrade a paying customer. See
            # _handle_invoice_payment_failed and expire_lapsed_subscriptions.
            SubscriptionStatus.PAST_DUE.value,
        ):
            plan = await self._repo.get_plan_by_id(subscription.plan_id)
            if plan is not None:
                return plan

        starter = await self._repo.get_plan_by_code("starter")
        if starter is None:
            raise RuntimeError(
                "Starter plan is not seeded — cannot resolve a default plan"
            )
        return starter

    async def get_current_subscription(self, organization_id: uuid.UUID) -> dict:
        """Everything the billing page needs to show "what am I on right
        now": the effective plan plus renewal details if there's an actual
        paid subscription row (Starter has none — null subscription = free
        tier, same convention as get_effective_plan).
        """
        plan = await self.get_effective_plan(organization_id)
        subscription = await self._repo.get_subscription_for_organization(
            organization_id
        )
        if subscription is not None and subscription.status == SubscriptionStatus.ACTIVE.value:
            return {
                "plan": plan,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }
        return {
            "plan": plan,
            "status": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

    async def cancel_subscription(self, organization_id: uuid.UUID) -> Subscription:
        """Cancel the organization's paid subscription at period end.

        Doesn't revoke access immediately — the org already paid for the
        current period, so it keeps working until `current_period_end`,
        same as most SaaS cancellation UX. `expire_lapsed_subscriptions`
        (run by the periodic sweep) is what actually drops the org back to
        Starter once that date passes.

        Also tells Paystack to stop auto-charging, when we have the codes
        to do so (set by the subscription.create webhook — see
        `_handle_subscription_create`). A subscription still on one-off
        billing (no provider_subscription_id yet, e.g. its plan has no
        provider_plan_code configured) has nothing to cancel on Paystack's
        side, so that call is skipped rather than failing.
        """
        subscription = await self._repo.get_subscription_for_organization(
            organization_id
        )
        if subscription is None or subscription.status != SubscriptionStatus.ACTIVE.value:
            raise NoActiveSubscriptionException()

        if subscription.cancel_at_period_end:
            return subscription  # already scheduled to cancel — idempotent

        if subscription.provider_subscription_id and subscription.provider_email_token:
            try:
                await self._adapter.cancel_subscription(
                    subscription.provider_subscription_id,
                    subscription.provider_email_token,
                )
            except Exception:
                # Don't block the user's cancellation on a Paystack API
                # hiccup — they're actively trying to stop being charged,
                # and our own expiry sweep will still drop them to Starter
                # at period end regardless of Paystack's state. But this
                # needs manual follow-up: if Paystack's side wasn't
                # actually disabled, it may still attempt to auto-charge
                # next cycle.
                logger.exception(
                    f"Failed to cancel Paystack subscription "
                    f"{subscription.provider_subscription_id} for org "
                    f"{organization_id} — cancelling locally anyway, "
                    "needs manual verification on Paystack's side"
                )

        return await self._repo.update_subscription(
            subscription.id,
            {"cancel_at_period_end": True, "canceled_at": datetime.now(UTC)},
        )

    async def assert_professional_or_above(self, organization_id: uuid.UUID) -> None:
        """Gate a feature to paid plans. Starter is the only plan this
        excludes — Professional and Enterprise both pass, since Enterprise
        is a strict superset of Professional's features.
        """
        plan = await self.get_effective_plan(organization_id)
        if plan.code == "starter":
            raise PlanUpgradeRequiredException()

    async def assert_can_post_job(self, organization_id: uuid.UUID | None) -> None:
        """Gate job creation to the organization's plan's active-posting
        limit. Counts active jobs across every member of the org, not just
        the caller — the quota is shared, not per-login.

        An employer with no organization at all shouldn't occur in a real
        request (every employer gets one at registration, see Phase 1a),
        but guard it explicitly rather than let None flow into an
        `organization_id IS NULL` query that could match unrelated rows.
        """
        if organization_id is None:
            return

        plan = await self.get_effective_plan(organization_id)
        if plan.job_posting_limit is None:
            return  # unlimited on this plan

        stmt = (
            select(func.count(Job.id))
            .join(User, User.id == Job.employer_id)
            .where(User.organization_id == organization_id, Job.status == "ACTIVE")
        )
        result = await self._db.execute(stmt)
        active_count = result.scalar_one()
        if active_count >= plan.job_posting_limit:
            raise JobPostingLimitExceededException(
                f"Your plan allows {plan.job_posting_limit} active job posting(s); "
                f"you currently have {active_count}."
            )

    async def start_credit_topup_checkout(
        self,
        *,
        organization_id: uuid.UUID,
        credit_package_code: str,
        customer_email: str,
        initiated_by_user_id: uuid.UUID,
    ) -> str:
        organization = await self._employer_repo.get_organization_by_id(organization_id)
        if organization is None:
            raise ValueError(f"Organization with id {organization_id} not found")

        credit_package = await self._repo.get_credit_package_by_code(
            credit_package_code
        )
        if not credit_package:
            raise CreditPackageNotFoundException(
                f"Credit package with code {credit_package_code} not found"
            )
        amount_kobo = credit_package.price_kobo

        # Look up any in-flight checkout BEFORE minting a reference — we can't
        # search by a reference that doesn't exist yet, so this has to run first.
        existing = await self._repo.get_pending_payment(
            organization_id=organization_id,
            purpose="CREDIT_TOPUP",
        )

        now = datetime.now(UTC)

        is_same_package = (
            existing is not None and existing.amount_kobo == credit_package.price_kobo
        )

        if (
            is_same_package
            and existing.checkout_url
            and existing.checkout_url_expires_at
            and existing.checkout_url_expires_at > now
        ):
            return existing.checkout_url  # still fresh — no Paystack call needed

        # Either no PENDING payment exists yet, or the one we found has an
        # expired/missing checkout link, or it's for a different package —
        # either way we need a fresh reference.
        reference = f"TOPUP-{uuid.uuid4()}"

        if existing is None:
            payment = await self._repo.create_payment(
                {
                    "organization_id": organization.id,
                    "subscription_id": None,  # top-up, never tied to a subscription
                    "purpose": "CREDIT_TOPUP",
                    "amount_kobo": amount_kobo,
                    "currency": "NGN",
                    "status": "PENDING",
                    "provider": "PAYSTACK",
                    "provider_reference": reference,
                    "initiated_by_user_id": initiated_by_user_id,
                    "credits_granted": credit_package.credits,
                }
            )
            # Commit now, before the Paystack call — this row must survive
            # even if the network call below fails.
            await self._db.commit()
        else:
            payment = existing
            payment.provider_reference = reference
            payment.amount_kobo = credit_package.price_kobo
            payment.credits_granted = credit_package.credits

        checkout_session = await self._adapter.create_checkout_session(
            amount_kobo=amount_kobo,
            currency="NGN",
            reference=reference,
            customer_email=customer_email,
            metadata={
                "organization_id": str(organization.id),
                "organization_name": organization.company_name,
                "purpose": "CREDIT_TOPUP",
            },
        )

        payment.checkout_url = checkout_session.checkout_url
        payment.checkout_url_expires_at = now + _CHECKOUT_URL_TTL
        await self._db.commit()

        return checkout_session.checkout_url

    async def handle_webhook(
        self, provider: str, raw_body: bytes, headers: dict[str, str]
    ):
        """
        Handle webhooks.
        """

        provider = provider.lower()
        if provider not in _WEBHOOK_SIGNATURE_HEADERS:
            raise ValueError(f"Unsupported payment provider: {provider}")

        # Verify Signature
        signature = headers.get(_WEBHOOK_SIGNATURE_HEADERS[provider], "")
        if not self._adapter.verify_webhook_signature(raw_body, signature):
            raise InvalidWebhookSignatureException()

        event = self._adapter.parse_webhook_event(raw_body)

        try:
            recorded_event = await self._repo.record_webhook_event(
                provider=provider.upper(),
                provider_event_id=event.provider_event_id,
                event_type=event.event_type,
                payload=event.payload,
            )
            await self._db.commit()
        except IntegrityError:
            await self._db.rollback()
            return  # duplicate delivery — already recorded, nothing more to do

        try:
            await self._process_webhook_event(event, recorded_event)
            recorded_event.processed_at = datetime.now(UTC)
            await self._db.commit()
        except Exception as e:
            await self._db.rollback()
            logger.exception(
                "Failed to process webhook event %s", recorded_event.provider_event_id
            )
            fresh_event = await self._repo.get_webhook_event_by_id(recorded_event.id)
            fresh_event.processing_error = str(e)
            await self._db.commit()

    async def _process_webhook_event(
        self, event: ParsedWebhookEvent, recorded_event: WebhookEvent
    ) -> None:
        if event.event_type == "charge.success" and event.reference:
            await self._handle_charge_success(event, recorded_event)
        elif event.event_type == "subscription.create":
            await self._handle_subscription_create(event)
        elif event.event_type == "invoice.payment_failed":
            await self._handle_invoice_payment_failed(event)
        # Every other event type (subscription.disable, subscription.not_renew,
        # invoice.update, ...): nothing acts on these yet — logged in the
        # webhook_events table for visibility, not silently dropped.

    async def _handle_charge_success(
        self, event: ParsedWebhookEvent, recorded_event: WebhookEvent
    ) -> None:
        payment = await self._repo.get_payment_by_reference(event.reference)
        if payment is None:
            # Not a reference we minted — this is what a Paystack-initiated
            # recurring-plan auto-charge looks like (renewal charges use a
            # Paystack-generated reference, never one of ours).
            await self._handle_possible_renewal_charge(event)
            return

        if payment.status == PaymentStatus.SUCCEEDED.value:
            return

        try:
            verified_transaction = await self._adapter.verify_transaction(
                event.reference
            )
        except PaystackVerificationError as e:
            logger.error(
                f"Failed to process webhook event {event.provider_event_id}: {e}"
            )
            fresh_event = await self._repo.get_webhook_event_by_id(recorded_event.id)
            fresh_event.processing_error = str(e)
            await self._db.commit()
            # Leave processed_at unset — this delivery genuinely wasn't
            # resolved, and handle_webhook's outer handler is the one place
            # that decides that, so re-raise rather than swallow it here.
            raise

        try:
            await self._finalize_verified_payment(payment, verified_transaction)
        except PaymentVerificationException as e:
            fresh_event = await self._repo.get_webhook_event_by_id(recorded_event.id)
            fresh_event.processing_error = str(e)
            await self._db.commit()
            raise

    async def _handle_possible_renewal_charge(self, event: ParsedWebhookEvent) -> None:
        """A charge.success for a reference we never minted — check whether
        it's Paystack auto-charging a subscription we know about (matched
        by the customer_code captured on that subscription's original
        charge) before writing anything.
        """
        data = event.payload.get("data", {})
        plan_data = data.get("plan") or {}
        customer_data = data.get("customer") or {}
        plan_code = plan_data.get("plan_code")
        customer_code = customer_data.get("customer_code")

        if not plan_code or not customer_code:
            logger.warning(f"webhook for unknown payment reference: {event.reference}")
            return

        subscription = await self._repo.get_subscription_by_provider_customer_code(
            customer_code
        )
        if subscription is None:
            logger.warning(
                f"charge.success for unrecognized reference {event.reference} "
                f"(customer_code={customer_code}) — no matching subscription"
            )
            return

        plan = await self._repo.get_plan_by_id(subscription.plan_id)
        if plan is None:
            logger.error(
                f"Subscription {subscription.id} has no resolvable plan — "
                f"cannot record renewal charge {event.reference}"
            )
            return

        try:
            verified_transaction = await self._adapter.verify_transaction(
                event.reference
            )
        except PaystackVerificationError as e:
            logger.error(f"Failed to verify renewal charge {event.reference}: {e}")
            raise

        if verified_transaction.status not in ("success", "successful"):
            return  # Paystack's own record doesn't confirm it — do nothing

        await self._repo.create_payment(
            {
                "organization_id": subscription.organization_id,
                "subscription_id": subscription.id,
                "plan_id": plan.id,
                "purpose": "SUBSCRIPTION_RENEWAL",
                "amount_kobo": verified_transaction.amount_kobo,
                "currency": verified_transaction.currency,
                "status": PaymentStatus.SUCCEEDED.value,
                "provider": "PAYSTACK",
                "provider_reference": event.reference,
                "provider_customer_code": customer_code,
                "paid_at": verified_transaction.paid_at,
            }
        )
        await self._activate_subscription(subscription.organization_id, plan)

    async def _handle_subscription_create(self, event: ParsedWebhookEvent) -> None:
        """Paystack sends this once, right after the first charge on a
        recurring plan creates the actual Subscription object on their
        side. This event carries none of our own metadata, so correlate it
        back to an organization via the customer_code captured on that
        first charge (see `_finalize_verified_payment`).

        Paystack does NOT guarantee this arrives after `charge.success` —
        confirmed in a real test-mode subscribe, where subscription.create
        landed first. When that happens, the customer_code this needs
        doesn't exist on any Payment row yet, so linking is retried from
        the other direction once charge.success finalizes (see
        `_try_catch_up_subscription_link`) — this method just no-ops rather
        than erroring when it hits that ordering.
        """
        data = event.payload.get("data", {})
        subscription_code = data.get("subscription_code")
        email_token = data.get("email_token")
        customer_code = (data.get("customer") or {}).get("customer_code")

        if not subscription_code or not email_token or not customer_code:
            logger.warning(
                "subscription.create webhook missing subscription_code/"
                "email_token/customer_code — cannot link it"
            )
            return

        payment = await self._repo.get_latest_succeeded_payment_by_customer_code(
            customer_code
        )
        if payment is None:
            logger.info(
                f"subscription.create for customer_code {customer_code} arrived "
                "before its charge.success — will link once that finalizes"
            )
            return

        await self._link_subscription(
            payment.organization_id, subscription_code, email_token, customer_code
        )

    async def _link_subscription(
        self,
        organization_id: uuid.UUID,
        subscription_code: str,
        email_token: str,
        customer_code: str,
    ) -> None:
        """Attach Paystack's subscription identifiers to this organization's
        local Subscription row. Shared by `_handle_subscription_create`
        (the normal order) and `_try_catch_up_subscription_link` (when
        subscription.create arrived first) — one place applies the update.
        """
        subscription = await self._repo.get_subscription_for_organization(
            organization_id
        )
        if subscription is None:
            logger.warning(
                f"subscription.create but organization {organization_id} "
                "has no local Subscription row to attach it to"
            )
            return

        await self._repo.update_subscription(
            subscription.id,
            {
                "provider_subscription_id": subscription_code,
                "provider_email_token": email_token,
                "provider_customer_code": customer_code,
            },
        )

    async def _try_catch_up_subscription_link(
        self, organization_id: uuid.UUID, customer_code: str
    ) -> None:
        """Called right after a charge.success finalizes a subscription
        payment — checks for a `subscription.create` webhook that already
        arrived for this customer_code but couldn't be linked yet at the
        time (because this payment's customer_code didn't exist until now).
        No-ops if nothing's pending, or if already linked.
        """
        subscription = await self._repo.get_subscription_for_organization(
            organization_id
        )
        if subscription is None or subscription.provider_subscription_id:
            return  # nothing to attach to, or already linked

        event = await self._repo.get_recent_webhook_event_by_customer_code(
            provider="PAYSTACK",
            event_type="subscription.create",
            customer_code=customer_code,
        )
        if event is None:
            return

        data = event.payload.get("data", {})
        subscription_code = data.get("subscription_code")
        email_token = data.get("email_token")
        if not subscription_code or not email_token:
            return

        await self._link_subscription(
            organization_id, subscription_code, email_token, customer_code
        )

    async def _handle_invoice_payment_failed(self, event: ParsedWebhookEvent) -> None:
        """A renewal charge failed. Doesn't cut access immediately — moves
        the subscription to PAST_DUE (get_effective_plan treats that the
        same as ACTIVE) and emails whoever manages billing for this org.
        Access actually ends at current_period_end, via the same
        expire_lapsed_subscriptions sweep that handles explicit cancels —
        Paystack itself keeps retrying the charge in the meantime, and if
        one of those retries succeeds, _handle_possible_renewal_charge
        extends the period and _activate_subscription resets status back
        to ACTIVE.

        Verify this event's exact payload shape against Paystack's test
        dashboard before relying on it in production — invoice payload
        nesting has varied across their API versions.
        """
        logger.warning(f"invoice.payment_failed webhook received: {event.payload}")

        data = event.payload.get("data", {})
        customer_code = (
            (data.get("customer") or {}).get("customer_code")
            or (data.get("subscription") or {}).get("customer", {}).get("customer_code")
        )
        if not customer_code:
            logger.warning(
                "invoice.payment_failed missing a customer_code — cannot act on it"
            )
            return

        subscription = await self._repo.get_subscription_by_provider_customer_code(
            customer_code
        )
        if subscription is None or subscription.status != SubscriptionStatus.ACTIVE.value:
            return  # unrecognized, or already PAST_DUE/canceled — nothing new to do

        plan = await self._repo.get_plan_by_id(subscription.plan_id)
        if plan is None:
            return

        await self._repo.update_subscription(
            subscription.id, {"status": SubscriptionStatus.PAST_DUE.value}
        )

        managers = await self._employer_repo.list_billing_managers(
            subscription.organization_id
        )
        organization = await self._employer_repo.get_organization_by_id(
            subscription.organization_id
        )
        retry_by = subscription.current_period_end.strftime("%B %d, %Y")
        email_service = get_email_service()
        for manager in managers:
            try:
                await email_service.send_subscription_payment_failed(
                    recipient_email=manager.email,
                    company_name=organization.company_name if organization else None,
                    plan_name=plan.name,
                    retry_by=retry_by,
                )
            except Exception:
                logger.exception(
                    f"Failed to send payment-failed email to {manager.email}"
                )

    async def _finalize_verified_payment(
        self, payment: Payment, verified_transaction: TransactionResult
    ) -> None:
        """Apply a Paystack-confirmed transaction result to a payment.

        Shared by `_process_webhook_event` (triggered by an inbound webhook)
        and `reconcile_pending_payment` (triggered by the periodic sweep of
        payments stuck PENDING) — both need identical grant/notify/mark-failed
        behavior once they have a verified transaction in hand, so this is
        the one place that behavior lives rather than two copies that could
        drift apart.
        """
        verified_amount = verified_transaction.amount_kobo
        expected_amount = payment.amount_kobo

        if verified_amount != expected_amount:
            logger.error(
                f"Amount mismatch for payment {payment.id}: "
                f"expected {expected_amount}, got {verified_amount}"
            )
            raise PaymentVerificationException(
                f"Amount mismatch: expected {expected_amount}, got {verified_amount}"
            )

        if verified_transaction.status not in ("success", "successful"):
            # Amount matched, but Paystack's own record of this transaction
            # doesn't confirm success (e.g. abandoned/failed) — never grant
            # or notify on an unconfirmed payment, no matter what triggered
            # this check.
            logger.warning(
                f"Payment {payment.id} did not verify as successful "
                f"(status={verified_transaction.status})"
            )
            await self._repo.update_payment(
                payment.id, {"status": PaymentStatus.FAILED.value}
            )
            return

        # Only reachable once Paystack's own API has confirmed this exact
        # transaction succeeded — safe to grant and notify from here on.
        update_data = {
            "paid_at": verified_transaction.paid_at,
            "status": PaymentStatus.SUCCEEDED.value,
        }
        if verified_transaction.provider_customer_code:
            # Captured here, not just on subscription charges — this is
            # what lets the subscription.create webhook (which carries none
            # of our own metadata) correlate back to an organization later.
            update_data["provider_customer_code"] = (
                verified_transaction.provider_customer_code
            )
        await self._repo.update_payment(payment.id, update_data)

        notification_type = None
        notification_title = None
        notification_body = None

        if payment.purpose == "CREDIT_TOPUP" and payment.credits_granted:
            credits_service = CreditsService(self._db)
            await credits_service.grant(
                employer_id=payment.organization_id,
                amount=payment.credits_granted,
                reference_id=payment.id,
            )
            notification_type = "CREDIT_TOPUP_SUCCESS"
            notification_title = "Credits Added"
            notification_body = (
                f"{payment.credits_granted} credits have been added to your account."
            )
        elif payment.purpose in ("SUBSCRIPTION_INITIAL", "SUBSCRIPTION_RENEWAL"):
            plan = await self._repo.get_plan_by_id(payment.plan_id)
            if plan is None:
                logger.error(
                    f"Payment {payment.id} has purpose={payment.purpose} "
                    "but no resolvable plan_id — cannot activate subscription"
                )
            else:
                subscription = await self._activate_subscription(
                    payment.organization_id, plan
                )
                payment.subscription_id = subscription.id
                notification_type = "SUBSCRIPTION_ACTIVATED"
                notification_title = "Subscription Activated"
                notification_body = f"Your {plan.name} subscription is now active."

                if verified_transaction.provider_customer_code:
                    await self._try_catch_up_subscription_link(
                        payment.organization_id,
                        verified_transaction.provider_customer_code,
                    )

        if payment.initiated_by_user_id and notification_type:
            notification_repo = NotificationRepository(self._db)
            await notification_repo.create(
                recipient_id=payment.initiated_by_user_id,
                type=notification_type,
                title=notification_title,
                body=notification_body,
                entity_type="PAYMENT",
                entity_id=payment.id,
            )

    async def expire_lapsed_subscriptions(self) -> int:
        """Drop every subscription past its `current_period_end` back to
        Starter, for the two cases that mean "this org's paid period is
        genuinely over":

        - Explicitly canceled (`cancel_at_period_end=True`) — the org asked
          to stop paying, see `cancel_subscription`.
        - PAST_DUE (a renewal charge failed) whose grace period has run out
          without a successful retry — see `_handle_invoice_payment_failed`.

        An org that's still ACTIVE and never canceled or failed a charge is
        untouched — that's the "no recurring re-charge configured for this
        plan" case (no provider_plan_code set), not something this sweep
        should silently paper over.

        Returns the number of subscriptions expired, for the caller to log.
        """
        now = datetime.now(UTC)
        lapsed_cancellations = await self._repo.list_lapsed_cancellations(older_than=now)
        lapsed_past_due = await self._repo.list_lapsed_past_due(older_than=now)
        for subscription in [*lapsed_cancellations, *lapsed_past_due]:
            await self._repo.update_subscription(
                subscription.id, {"status": SubscriptionStatus.EXPIRED.value}
            )
        return len(lapsed_cancellations) + len(lapsed_past_due)

    async def reconcile_pending_payment(self, payment_id: uuid.UUID) -> None:
        """Actively resolve one payment stuck PENDING, by asking Paystack
        directly rather than waiting on a webhook that may never arrive.
        Caller (the Celery task) owns the commit, same as `handle_webhook`
        owns it for the webhook path.
        """
        payment = await self._repo.get_payment_by_id(payment_id)
        if payment is None or payment.status != PaymentStatus.PENDING.value:
            return  # already resolved (or never existed) — nothing to do

        try:
            verified_transaction = await self._adapter.verify_transaction(
                payment.provider_reference
            )
        except PaystackVerificationError as e:
            logger.error(f"Reconciliation verify failed for payment {payment_id}: {e}")
            return  # try again next run

        try:
            await self._finalize_verified_payment(payment, verified_transaction)
        except PaymentVerificationException:
            logger.error(f"Reconciliation amount mismatch for payment {payment_id}")

    async def verify_checkout(
        self, reference: str, requesting_organization_id: uuid.UUID
    ) -> Payment:
        """Actively confirm a checkout's status right after the customer is
        redirected back — the webhook may not have arrived yet, and the
        frontend shouldn't just sit on a blind "processing" spinner.

        Scoped to `requesting_organization_id` so one organization can't
        probe another's payment status by guessing a reference. Shares
        `_finalize_verified_payment` with the webhook handler and the
        reconciliation sweep — this is a third trigger for the same
        finalize logic, not a third copy of it.
        """
        payment = await self._repo.get_payment_by_reference(reference)
        if payment is None:
            raise NotFoundException("Payment not found")
        if payment.organization_id != requesting_organization_id:
            raise PermissionDeniedException(
                "This payment does not belong to your organization"
            )

        if payment.status != PaymentStatus.PENDING.value:
            return payment  # already resolved by the webhook or a prior verify call

        try:
            verified_transaction = await self._adapter.verify_transaction(reference)
        except PaystackVerificationError as e:
            logger.error(f"Verify-on-redirect failed for {reference}: {e}")
            return payment  # still PENDING — webhook/reconciliation will catch it later

        try:
            await self._finalize_verified_payment(payment, verified_transaction)
            await self._db.commit()
        except PaymentVerificationException:
            await self._db.rollback()

        return payment

    async def start_subscription_checkout(
        self,
        *,
        organization_id: uuid.UUID,
        plan_code: str,
        customer_email: str,
        initiated_by_user_id: uuid.UUID,
    ) -> SubscriptionCheckoutResult:
        """Start a subscription checkout, or activate/schedule a free plan.

        See `SubscriptionCheckoutResult` for the three possible outcomes —
        notably, switching to a free plan while an active paid subscription
        exists does NOT overwrite it immediately (that would silently
        discard whatever the org already paid for this period); it's
        scheduled to take effect at period end instead, the same as an
        explicit cancel.
        """
        organization = await self._employer_repo.get_organization_by_id(organization_id)
        if organization is None:
            raise ValueError(f"Organization with id {organization_id} not found")

        plan = await self._repo.get_plan_by_code(plan_code)
        if plan is None:
            raise PlanNotFoundException(f"Plan with code {plan_code} not found")

        if plan.price_kobo == 0:
            existing_subscription = await self._repo.get_subscription_for_organization(
                organization_id
            )
            if existing_subscription is not None and existing_subscription.status == (
                SubscriptionStatus.ACTIVE.value
            ):
                current_plan = await self._repo.get_plan_by_id(
                    existing_subscription.plan_id
                )
                if current_plan is not None and current_plan.price_kobo > 0:
                    # Already paying for something this period — don't lose
                    # that. Same effect as an explicit cancel, driven through
                    # cancel_subscription so there's one place deciding what
                    # "the org is moving off this plan" means.
                    await self.cancel_subscription(organization_id)
                    await self._db.commit()
                    return SubscriptionCheckoutResult(
                        checkout_url=None,
                        activated=False,
                        effective_at=existing_subscription.current_period_end,
                    )

            # No active paid subscription to protect — free to switch now.
            # Still write a Payment row (amount_kobo=0, already SUCCEEDED)
            # so billing history stays complete, matching how an
            # admin-comped subscription is recorded — no special "no
            # payment" case.
            payment = await self._repo.create_payment(
                {
                    "organization_id": organization.id,
                    "subscription_id": None,
                    "plan_id": plan.id,
                    "purpose": "SUBSCRIPTION_INITIAL",
                    "amount_kobo": 0,
                    "currency": plan.currency,
                    "status": PaymentStatus.SUCCEEDED.value,
                    "provider": "PAYSTACK",
                    "provider_reference": f"FREE-{uuid.uuid4()}",
                    "initiated_by_user_id": initiated_by_user_id,
                    "paid_at": datetime.now(UTC),
                }
            )
            subscription = await self._activate_subscription(organization_id, plan)
            payment.subscription_id = subscription.id
            await self._db.commit()
            return SubscriptionCheckoutResult(checkout_url=None, activated=True)

        # Paid plan — same shape as start_credit_topup_checkout: reuse a
        # still-fresh pending checkout for the same plan, otherwise mint a
        # new reference and create/refresh the PENDING payment row.
        existing = await self._repo.get_pending_payment(
            organization_id=organization_id, purpose="SUBSCRIPTION_INITIAL"
        )

        now = datetime.now(UTC)
        is_same_plan = existing is not None and existing.plan_id == plan.id

        if (
            is_same_plan
            and existing.checkout_url
            and existing.checkout_url_expires_at
            and existing.checkout_url_expires_at > now
        ):
            return SubscriptionCheckoutResult(
                checkout_url=existing.checkout_url, activated=False
            )

        reference = f"SUB-{uuid.uuid4()}"

        if existing is None:
            payment = await self._repo.create_payment(
                {
                    "organization_id": organization.id,
                    "subscription_id": None,
                    "plan_id": plan.id,
                    "purpose": "SUBSCRIPTION_INITIAL",
                    "amount_kobo": plan.price_kobo,
                    "currency": plan.currency,
                    "status": "PENDING",
                    "provider": "PAYSTACK",
                    "provider_reference": reference,
                    "initiated_by_user_id": initiated_by_user_id,
                }
            )
            # Commit now, before the Paystack call — this row must survive
            # even if the network call below fails.
            await self._db.commit()
        else:
            payment = existing
            payment.provider_reference = reference
            payment.plan_id = plan.id
            payment.amount_kobo = plan.price_kobo

        checkout_session = await self._adapter.create_checkout_session(
            amount_kobo=plan.price_kobo,
            currency=plan.currency,
            reference=reference,
            customer_email=customer_email,
            metadata={
                "organization_id": str(organization.id),
                "organization_name": organization.company_name,
                "purpose": "SUBSCRIPTION_INITIAL",
                "plan_code": plan.code,
            },
            # When set, this attaches the charge to a Paystack Plan so it
            # auto-renews (see subscription.create handling below). If the
            # plan hasn't been provisioned on Paystack's side yet, this is
            # just None and the charge stays one-off — no renewal, exactly
            # today's behavior.
            provider_plan_code=plan.provider_plan_code,
        )

        payment.checkout_url = checkout_session.checkout_url
        payment.checkout_url_expires_at = now + _CHECKOUT_URL_TTL
        await self._db.commit()

        return SubscriptionCheckoutResult(
            checkout_url=checkout_session.checkout_url, activated=False
        )

    async def _activate_subscription(
        self, organization_id: uuid.UUID, plan: Plan
    ) -> Subscription:
        """Create or update the organization's Subscription row to ACTIVE
        on `plan`, for one billing period starting now. Shared by the free-
        plan path in `start_subscription_checkout` and the paid-plan path
        in `_finalize_verified_payment` — one place decides what
        "activated" means, not two.
        """
        now = datetime.now(UTC)
        period_length = (
            timedelta(days=365) if plan.interval == "ANNUAL" else timedelta(days=30)
        )
        data = {
            "plan_id": plan.id,
            "status": SubscriptionStatus.ACTIVE.value,
            "provider": "PAYSTACK",
            "current_period_start": now,
            "current_period_end": now + period_length,
            "cancel_at_period_end": False,
            "canceled_at": None,
        }

        existing = await self._repo.get_subscription_for_organization(organization_id)
        if existing is None:
            return await self._repo.create_subscription(
                {"organization_id": organization_id, **data}
            )
        return await self._repo.update_subscription(existing.id, data)
