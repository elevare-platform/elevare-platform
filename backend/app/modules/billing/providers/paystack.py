"""Paystack adapter — https://paystack.com/docs/api/

Paystack's "Initialize Transaction" endpoint doubles as checkout-session
creation for both one-off charges and the first charge of a subscription
(pass `plan` in the payload to attach a Paystack Plan). Webhook signatures
are HMAC-SHA512 of the raw request body, keyed by the secret key, sent in
the `x-paystack-signature` header.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime

import httpx

from app.core.exceptions import PaystackVerificationError
from app.modules.billing.providers.base import (
    CheckoutSession,
    ParsedWebhookEvent,
    PaymentAdapter,
    TransactionResult,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.paystack.co"


class PaystackAdapter(PaymentAdapter):
    def __init__(self, secret_key: str) -> None:
        self._secret_key = secret_key
        self._headers = {
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        }

    async def create_checkout_session(
        self,
        *,
        amount_kobo: int,
        currency: str,
        reference: str,
        customer_email: str,
        metadata: dict,
        provider_plan_code: str | None = None,
    ) -> CheckoutSession:
        if not self._secret_key:
            # Paystack isn't configured yet (business verification pending) —
            # fail cleanly here rather than let a "Bearer None" request hit
            # Paystack's API and surface as a raw, unhandled crash. Free-plan
            # subscriptions never reach this path, so Starter stays usable
            # regardless of Paystack's status.
            from app.core.exceptions import PaymentsNotConfiguredError

            raise PaymentsNotConfiguredError()

        from app.core.config import settings

        payload = {
            "email": customer_email,
            "amount": amount_kobo,
            "currency": currency,
            "reference": reference,
            "metadata": metadata,
            # Without this, Paystack falls back to whatever's configured in
            # the dashboard (or nothing) — setting it explicitly means the
            # redirect always lands back on the right frontend regardless of
            # dashboard config, and works across dev/staging/prod unchanged.
            # Paystack appends ?reference=...&trxref=... itself on redirect.
            "callback_url": f"{settings.app_url.rstrip('/')}/employer/billing/verify",
        }
        if provider_plan_code:
            # Attaches this charge to a Paystack Plan — Paystack then
            # creates a real Subscription object and auto-charges the
            # customer's saved authorization at renewal, instead of this
            # being a one-off charge. See subscription.create webhook
            # handling in BillingService._handle_subscription_create.
            payload["plan"] = provider_plan_code
        async with httpx.AsyncClient(
            base_url=_BASE_URL, headers=self._headers, timeout=30
        ) as client:
            response = await client.post("/transaction/initialize", json=payload)
            response.raise_for_status()
            body = response.json()

        data = body["data"]
        return CheckoutSession(
            reference=data["reference"],
            checkout_url=data["authorization_url"],
            raw=body,
        )

    async def verify_transaction(self, reference: str) -> TransactionResult:
        try:
            async with httpx.AsyncClient(
                base_url=_BASE_URL, headers=self._headers, timeout=30
            ) as client:
                response = await client.get(f"/transaction/verify/{reference}")
                response.raise_for_status()
                body = response.json()

            if body.get("status") is True:
                data = body["data"]
                paid_at = None
                if data.get("paid_at"):
                    paid_at = datetime.fromisoformat(
                        data["paid_at"].replace("Z", "+00:00")
                    )

                return TransactionResult(
                    reference=data["reference"],
                    status=data.get("status"),
                    amount_kobo=data.get("amount", 0),
                    currency=data.get("currency", "NGN"),
                    paid_at=paid_at,
                    provider_customer_code=(data.get("customer") or {}).get(
                        "customer_code"
                    ),
                    raw=body,
                )
            else:
                error_msg = body.get("message", "verification failed")
                logger.error(
                    f"Payment verification failed for " f"{reference}: {error_msg}"
                )
                raise PaystackVerificationError(error_msg)

        except httpx.HTTPError as e:
            # httpx.ConnectError / httpx.RequestError are both subclasses of
            # HTTPError — one clause here already covers them.
            logger.error(f"HTTP error verifying payment {reference}: {e}")
            raise PaystackVerificationError(f"Verification request failed: {e}") from e

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        expected = hmac.new(
            self._secret_key.encode("utf-8"), payload, hashlib.sha512
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    def parse_webhook_event(self, payload: bytes) -> ParsedWebhookEvent:
        body = json.loads(payload)
        data = body.get("data", {})
        event_type = body.get("event", "")

        # Paystack doesn't send one universal id field across all its
        # webhook payload shapes — only charge.* events carry `reference`.
        # subscription.* events carry `subscription_code` instead, and
        # everything else falls back to the object's numeric `id`. The
        # (dedup_key, event) pair is unique per delivery in practice, and
        # webhook_events' dedup constraint is on (provider, provider_event_id).
        reference = data.get("reference") or None
        if reference:
            dedup_key = reference
        elif event_type.startswith("subscription."):
            dedup_key = data.get("subscription_code", "")
        elif event_type.startswith("invoice."):
            dedup_key = data.get("invoice_code") or str(data.get("id", ""))
        else:
            dedup_key = str(data.get("id", ""))

        if not dedup_key:
            raise ValueError(f"Webhook payload missing a usable id for event {event_type}")

        event_id = f"{dedup_key}:{event_type}"

        return ParsedWebhookEvent(
            provider_event_id=event_id,
            event_type=event_type,
            reference=reference,
            payload=body,
        )

    async def cancel_subscription(self, subscription_code: str, email_token: str) -> None:
        async with httpx.AsyncClient(
            base_url=_BASE_URL, headers=self._headers, timeout=30
        ) as client:
            response = await client.post(
                "/subscription/disable",
                json={"code": subscription_code, "token": email_token},
            )
            response.raise_for_status()

    async def create_plan(
        self, *, name: str, amount_kobo: int, interval: str, currency: str = "NGN"
    ) -> str:
        """Create a Paystack Plan and return its plan_code. One-off
        provisioning call — run manually (e.g. from a shell/script with
        live credentials) once per paid Plan, then store the resulting
        code on `Plan.provider_plan_code`. Not called from any request path.
        """
        async with httpx.AsyncClient(
            base_url=_BASE_URL, headers=self._headers, timeout=30
        ) as client:
            response = await client.post(
                "/plan",
                json={
                    "name": name,
                    "amount": amount_kobo,
                    "interval": interval,
                    "currency": currency,
                },
            )
            response.raise_for_status()
            body = response.json()
        return body["data"]["plan_code"]


def get_paystack_adapter() -> PaystackAdapter:
    from app.core.config import settings

    if not settings.paystack_secret_key:
        raise RuntimeError("PAYSTACK_SECRET_KEY is not configured")
    return PaystackAdapter(settings.paystack_secret_key)
