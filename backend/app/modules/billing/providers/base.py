"""Abstract payment provider interface.

Mirrors `ingestion/adapters/base.py`: `BillingService` depends only on
this interface, never on a provider SDK directly, so adding a second
provider (e.g. Flutterwave, as a resilience hedge — see the architecture
review §6/§10.12) is a new adapter file, not a service rewrite.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CheckoutSession:
    """A provider-hosted checkout the caller redirects the user to."""

    reference: str
    checkout_url: str
    raw: dict = field(default_factory=dict)


@dataclass
class TransactionResult:
    """The result of verifying a single payment reference."""

    reference: str
    status: str
    amount_kobo: int
    currency: str
    paid_at: datetime | None
    provider_customer_code: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class ParsedWebhookEvent:
    """A provider webhook payload, normalised into what the handler needs."""

    provider_event_id: str
    event_type: str
    reference: str | None
    payload: dict


class PaymentAdapter(ABC):
    """Abstract base for all payment provider adapters.

    Each provider (Paystack, Flutterwave) implements this interface. The
    billing service only ever talks to this interface — adding a new
    provider is an adapter, not a service change.
    """

    @abstractmethod
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
        """Start a provider-hosted checkout and return its redirect URL.

        `provider_plan_code`, when given, attaches this charge to a
        provider-side recurring plan — the provider then auto-charges the
        customer's saved authorization at renewal instead of this being a
        one-off charge.
        """

    @abstractmethod
    async def verify_transaction(self, reference: str) -> TransactionResult:
        """Actively check a transaction's status by reference.

        Called both from the post-redirect verify endpoint (the customer
        may land back before the webhook arrives) and from the periodic
        reconciliation task for payments stuck PENDING.
        """

    @abstractmethod
    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify an inbound webhook's signature before any DB write."""

    @abstractmethod
    def parse_webhook_event(self, payload: bytes) -> ParsedWebhookEvent:
        """Normalise a verified webhook payload into a `ParsedWebhookEvent`."""

    @abstractmethod
    async def cancel_subscription(self, subscription_code: str, email_token: str) -> None:
        """Cancel a subscription on the provider's side.

        Paystack requires both values — the subscription code and a
        separate email token issued on `subscription.create` — not the
        same identifier twice.
        """
