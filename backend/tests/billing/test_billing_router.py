"""Tests for the billing router — public plan/package catalog, checkout,
payment history, and verify-on-redirect endpoints.
"""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.modules.auth.jwt_handler import create_token_pair
from app.modules.billing.models import Payment, Subscription
from app.modules.billing.providers.base import CheckoutSession, TransactionResult
from app.modules.employer.enums import OrganizationRole
from app.modules.users.models import User
from tests.conftest import (
    make_organization_for,
    make_register_data,
    make_subscription_for,
)


async def register_and_promote(
    client, db_session, role: str, org_role: str = "OWNER"
) -> tuple[str, User]:
    """Register a user, promote to `role`, and (for EMPLOYER) create an
    Organization with the given org_role. Returns (access_token, user).
    """
    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = role
    user.account_status = "ACTIVE"
    await db_session.flush()

    if role == "EMPLOYER":
        await make_organization_for(db_session, user, company_name="Test Corp")
        user.organization_role = org_role
        await db_session.flush()

    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"], user


# --- Public catalog ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_plans_returns_seeded_plans(client):
    response = await client.get("/api/v1/billing/plans")
    assert response.status_code == 200
    codes = {p["code"] for p in response.json()}
    assert {"starter", "professional"}.issubset(codes)


@pytest.mark.asyncio
async def test_list_credit_packages_returns_seeded_packages(client):
    response = await client.get("/api/v1/billing/credit-packages")
    assert response.status_code == 200
    codes = {p["code"] for p in response.json()}
    assert {"starter_pack", "growth_pack", "scale_pack"}.issubset(codes)


# --- Checkout: org-role gate --------------------------------------------


@pytest.mark.asyncio
async def test_start_credit_checkout_rejects_plain_member(client, db_session):
    token, _ = await register_and_promote(
        client, db_session, "EMPLOYER", org_role=OrganizationRole.MEMBER.value
    )
    response = await client.post(
        "/api/v1/billing/credits/checkout",
        json={"credit_package_code": "starter_pack"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_start_credit_checkout_success_for_owner(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    fake_session = CheckoutSession(
        reference="TOPUP-fake", checkout_url="https://paystack.test/pay/fake"
    )
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.create_checkout_session",
        AsyncMock(return_value=fake_session),
    ):
        response = await client.post(
            "/api/v1/billing/credits/checkout",
            json={"credit_package_code": "starter_pack"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["checkout_url"] == "https://paystack.test/pay/fake"

    result = await db_session.execute(
        select(Payment).where(Payment.organization_id == user.organization_id)
    )
    payment = result.scalar_one()
    assert payment.status == "PENDING"
    assert payment.credits_granted == 10  # starter_pack


@pytest.mark.asyncio
async def test_start_credit_checkout_unknown_package_returns_404(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")
    response = await client.post(
        "/api/v1/billing/credits/checkout",
        json={"credit_package_code": "does_not_exist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Subscription checkout ---------------------------------------------------


@pytest.mark.asyncio
async def test_start_subscription_checkout_rejects_plain_member(client, db_session):
    token, _ = await register_and_promote(
        client, db_session, "EMPLOYER", org_role=OrganizationRole.MEMBER.value
    )
    response = await client.post(
        "/api/v1/billing/subscription/checkout",
        json={"plan_code": "professional"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_start_subscription_checkout_free_plan_activates_immediately(
    client, db_session
):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    response = await client.post(
        "/api/v1/billing/subscription/checkout",
        json={"plan_code": "starter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checkout_url"] is None
    assert body["activated"] is True

    result = await db_session.execute(
        select(Subscription).where(Subscription.organization_id == user.organization_id)
    )
    subscription = result.scalar_one()
    assert subscription.status == "ACTIVE"


@pytest.mark.asyncio
async def test_start_subscription_checkout_paid_plan_returns_checkout_url(
    client, db_session
):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    fake_session = CheckoutSession(
        reference="SUB-fake", checkout_url="https://paystack.test/pay/sub-fake"
    )
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.create_checkout_session",
        AsyncMock(return_value=fake_session),
    ):
        response = await client.post(
            "/api/v1/billing/subscription/checkout",
            json={"plan_code": "professional"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["checkout_url"] == "https://paystack.test/pay/sub-fake"
    assert body["activated"] is False

    result = await db_session.execute(
        select(Payment).where(
            Payment.organization_id == user.organization_id,
            Payment.purpose == "SUBSCRIPTION_INITIAL",
        )
    )
    payment = result.scalar_one()
    assert payment.status == "PENDING"
    assert payment.amount_kobo == 4_500_000


@pytest.mark.asyncio
async def test_start_subscription_checkout_unknown_plan_returns_404(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")
    response = await client.post(
        "/api/v1/billing/subscription/checkout",
        json={"plan_code": "does_not_exist"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


# --- Downgrade protection: switching to a free plan while a paid --------
# --- subscription is active must not overwrite it immediately -----------


@pytest.mark.asyncio
async def test_downgrade_to_free_plan_schedules_instead_of_overwriting(
    client, db_session
):
    """An org on Professional hitting subscription/checkout with plan_code
    'starter' must not lose its paid period — it should be scheduled to
    lapse at period end, same as an explicit cancel.
    """
    from app.modules.billing.models import Subscription
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session, organization, plan_code="professional"
    )
    original_period_end = subscription.current_period_end

    response = await client.post(
        "/api/v1/billing/subscription/checkout",
        json={"plan_code": "starter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checkout_url"] is None
    assert body["activated"] is False
    assert body["effective_at"] is not None

    result = await db_session.execute(
        select(Subscription).where(Subscription.organization_id == organization.id)
    )
    reloaded = result.scalar_one()
    # Still on Professional, still ACTIVE, still the same period — only the
    # cancellation flag changed, nothing was overwritten.
    assert reloaded.status == "ACTIVE"
    assert reloaded.cancel_at_period_end is True
    assert reloaded.current_period_end == original_period_end

    response = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.json()["plan"]["code"] == "professional"


@pytest.mark.asyncio
async def test_switch_to_free_plan_activates_immediately_with_no_paid_subscription(
    client, db_session
):
    """A fresh org (or one already on Starter) switching to the free plan
    still activates immediately — there's no paid time to protect.
    """
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.post(
        "/api/v1/billing/subscription/checkout",
        json={"plan_code": "starter"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checkout_url"] is None
    assert body["activated"] is True
    assert body["effective_at"] is None


# --- Recurring billing (Phase 4): Paystack subscription webhooks --------


async def _post_webhook(client, event_type, data):
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.verify_webhook_signature",
        return_value=True,
    ):
        return await client.post(
            "/api/v1/billing/webhooks/paystack",
            json={"event": event_type, "data": data},
            headers={"x-paystack-signature": "fake"},
        )


@pytest.mark.asyncio
async def test_webhook_subscription_create_links_subscription(client, db_session):
    from app.modules.billing.models import Subscription
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(db_session, organization, plan_code="professional")

    # The correlating signal: a succeeded subscription payment already
    # carrying the Paystack customer_code, captured off the original charge.
    payment = Payment(
        organization_id=organization.id,
        subscription_id=None,
        plan_id=None,
        purpose="SUBSCRIPTION_INITIAL",
        amount_kobo=4_500_000,
        currency="NGN",
        status="SUCCEEDED",
        provider="PAYSTACK",
        provider_reference="SUB-linked",
        provider_customer_code="CUS_link_test",
        initiated_by_user_id=user.id,
    )
    db_session.add(payment)
    await db_session.flush()
    await db_session.commit()

    response = await _post_webhook(
        client,
        "subscription.create",
        {
            "subscription_code": "SUB_code_123",
            "email_token": "email_tok_123",
            "customer": {"customer_code": "CUS_link_test"},
            "plan": {"plan_code": "PLN_professional"},
        },
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Subscription).where(Subscription.organization_id == organization.id)
    )
    subscription = result.scalar_one()
    assert subscription.provider_subscription_id == "SUB_code_123"
    assert subscription.provider_email_token == "email_tok_123"
    assert subscription.provider_customer_code == "CUS_link_test"


@pytest.mark.asyncio
async def test_webhook_subscription_create_before_charge_success_links_on_catch_up(
    client, db_session
):
    """Paystack does not guarantee subscription.create arrives after the
    charge.success it depends on for correlation — confirmed in a real
    test-mode subscribe, where subscription.create landed first. When that
    happens, linking must not be lost: it should complete once
    charge.success finalizes and captures the customer_code.
    """
    from app.modules.billing.models import Plan, Subscription
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(db_session, organization, plan_code="professional")

    plan_result = await db_session.execute(
        select(Plan).where(Plan.code == "professional")
    )
    plan = plan_result.scalar_one()
    payment = Payment(
        organization_id=organization.id,
        subscription_id=None,
        plan_id=plan.id,
        purpose="SUBSCRIPTION_INITIAL",
        amount_kobo=plan.price_kobo,
        currency="NGN",
        status="PENDING",
        provider="PAYSTACK",
        provider_reference="SUB-order-test",
        initiated_by_user_id=user.id,
    )
    db_session.add(payment)
    await db_session.flush()
    await db_session.commit()

    # subscription.create arrives FIRST — no Payment has this customer_code
    # yet, so it can't link (this is the exact sequence observed live).
    response = await _post_webhook(
        client,
        "subscription.create",
        {
            "subscription_code": "SUB_order_test",
            "email_token": "email_tok_order_test",
            "customer": {"customer_code": "CUS_order_test"},
            "plan": {"plan_code": "PLN_professional"},
        },
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Subscription).where(Subscription.organization_id == organization.id)
    )
    subscription = result.scalar_one()
    assert subscription.provider_subscription_id is None  # not linked yet

    # charge.success arrives SECOND and finalizes the payment.
    fake_result = TransactionResult(
        reference="SUB-order-test",
        status="success",
        amount_kobo=plan.price_kobo,
        currency="NGN",
        paid_at=None,
        provider_customer_code="CUS_order_test",
    )
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.verify_transaction",
        AsyncMock(return_value=fake_result),
    ):
        response = await _post_webhook(
            client,
            "charge.success",
            {"reference": "SUB-order-test"},
        )
    assert response.status_code == 200

    await db_session.refresh(subscription)
    assert subscription.provider_subscription_id == "SUB_order_test"
    assert subscription.provider_email_token == "email_tok_order_test"
    assert subscription.provider_customer_code == "CUS_order_test"


@pytest.mark.asyncio
async def test_webhook_charge_success_unknown_reference_records_renewal(
    client, db_session
):
    """A charge.success for a reference we never minted, but tied to a
    customer_code we recognize, must be treated as an auto-renewal: a new
    Payment row and an extended subscription period — not silently dropped.
    """
    from app.modules.billing.models import Subscription
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        provider_customer_code="CUS_renew_test",
    )
    original_period_end = subscription.current_period_end

    fake_result = TransactionResult(
        reference="PSK_auto_renewal_1",
        status="success",
        amount_kobo=4_500_000,
        currency="NGN",
        paid_at=None,
    )
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.verify_transaction",
        AsyncMock(return_value=fake_result),
    ):
        response = await _post_webhook(
            client,
            "charge.success",
            {
                "reference": "PSK_auto_renewal_1",
                "plan": {"plan_code": "PLN_professional"},
                "customer": {"customer_code": "CUS_renew_test"},
            },
        )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Payment).where(Payment.provider_reference == "PSK_auto_renewal_1")
    )
    renewal_payment = result.scalar_one()
    assert renewal_payment.purpose == "SUBSCRIPTION_RENEWAL"
    assert renewal_payment.status == "SUCCEEDED"
    assert renewal_payment.organization_id == organization.id

    await db_session.refresh(subscription)
    assert subscription.current_period_end > original_period_end


@pytest.mark.asyncio
async def test_cancel_subscription_calls_paystack_when_codes_present(
    client, db_session
):
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        provider_subscription_id="SUB_cancel_me",
        provider_email_token="tok_cancel_me",
    )

    mock_cancel = AsyncMock(return_value=None)
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.cancel_subscription",
        mock_cancel,
    ):
        response = await client.post(
            "/api/v1/billing/subscription/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    mock_cancel.assert_awaited_once_with("SUB_cancel_me", "tok_cancel_me")


# --- Failed renewal charges: grace period, not immediate downgrade ------


@pytest.mark.asyncio
async def test_webhook_invoice_payment_failed_marks_past_due_and_keeps_access(
    client, db_session
):
    from app.modules.billing.models import Subscription
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        provider_customer_code="CUS_past_due_test",
    )

    response = await _post_webhook(
        client,
        "invoice.payment_failed",
        {
            "id": 12345,
            "invoice_code": "INV_test_1",
            "customer": {"customer_code": "CUS_past_due_test"},
        },
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(Subscription).where(Subscription.organization_id == organization.id)
    )
    subscription = result.scalar_one()
    assert subscription.status == "PAST_DUE"

    # Grace period — still resolves to the paid plan, not Starter.
    subscription_response = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert subscription_response.json()["plan"]["code"] == "professional"


@pytest.mark.asyncio
async def test_expire_lapsed_subscriptions_expires_past_due_after_grace_period(
    client, db_session
):
    from datetime import UTC, datetime, timedelta

    from app.modules.billing.service import BillingService
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        status="PAST_DUE",
        current_period_end=datetime.now(UTC) - timedelta(days=1),
    )

    service = BillingService(db_session)
    expired_count = await service.expire_lapsed_subscriptions()
    await db_session.commit()

    assert expired_count == 1
    await db_session.refresh(subscription)
    assert subscription.status == "EXPIRED"

    plan = await service.get_effective_plan(user.organization_id)
    assert plan.code == "starter"


@pytest.mark.asyncio
async def test_expire_lapsed_subscriptions_leaves_past_due_within_grace_period(
    client, db_session
):
    from app.modules.billing.service import BillingService
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session, organization, plan_code="professional", status="PAST_DUE"
    )

    service = BillingService(db_session)
    expired_count = await service.expire_lapsed_subscriptions()
    await db_session.commit()

    assert expired_count == 0
    await db_session.refresh(subscription)
    assert subscription.status == "PAST_DUE"

    plan = await service.get_effective_plan(user.organization_id)
    assert plan.code == "professional"


# --- Payment history ---------------------------------------------------------


@pytest.mark.asyncio
async def test_list_payments_returns_org_payments(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    payment = Payment(
        organization_id=user.organization_id,
        subscription_id=None,
        purpose="CREDIT_TOPUP",
        amount_kobo=1_500_000,
        currency="NGN",
        status="SUCCEEDED",
        provider="PAYSTACK",
        provider_reference="TOPUP-existing",
        initiated_by_user_id=user.id,
        credits_granted=10,
    )
    db_session.add(payment)
    await db_session.flush()

    response = await client.get(
        "/api/v1/billing/payments", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["provider_reference"] == "TOPUP-existing"
    assert body[0]["organization_name"] == "Test Corp"


# --- Verify-on-redirect: cross-org protection --------------------------------


@pytest.mark.asyncio
async def test_verify_checkout_rejects_other_organizations_payment(client, db_session):
    _, owner_a = await register_and_promote(client, db_session, "EMPLOYER")
    payment = Payment(
        organization_id=owner_a.organization_id,
        subscription_id=None,
        purpose="CREDIT_TOPUP",
        amount_kobo=1_500_000,
        currency="NGN",
        status="PENDING",
        provider="PAYSTACK",
        provider_reference="TOPUP-cross-org",
        initiated_by_user_id=owner_a.id,
        credits_granted=10,
    )
    db_session.add(payment)
    await db_session.flush()

    token_b, _ = await register_and_promote(client, db_session, "EMPLOYER")
    response = await client.get(
        "/api/v1/billing/checkout/TOPUP-cross-org/verify",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_verify_checkout_finalizes_confirmed_payment(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    payment = Payment(
        organization_id=user.organization_id,
        subscription_id=None,
        purpose="CREDIT_TOPUP",
        amount_kobo=1_500_000,
        currency="NGN",
        status="PENDING",
        provider="PAYSTACK",
        provider_reference="TOPUP-verify-me",
        initiated_by_user_id=user.id,
        credits_granted=10,
    )
    db_session.add(payment)
    await db_session.flush()

    fake_result = TransactionResult(
        reference="TOPUP-verify-me",
        status="success",
        amount_kobo=1_500_000,
        currency="NGN",
        paid_at=None,
    )
    with patch(
        "app.modules.billing.providers.paystack.PaystackAdapter.verify_transaction",
        AsyncMock(return_value=fake_result),
    ):
        response = await client.get(
            "/api/v1/billing/checkout/TOPUP-verify-me/verify",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "SUCCEEDED"


# --- Current subscription ----------------------------------------------


@pytest.mark.asyncio
async def test_get_current_subscription_defaults_to_starter(client, db_session):
    """No Subscription row at all — org is implicitly on Starter, no renewal info."""
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["code"] == "starter"
    assert body["status"] is None
    assert body["current_period_end"] is None


@pytest.mark.asyncio
async def test_get_current_subscription_returns_active_paid_plan(client, db_session):
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(db_session, organization, plan_code="professional")

    response = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["code"] == "professional"
    assert body["status"] == "ACTIVE"
    assert body["current_period_end"] is not None


# --- Master gating switch (PLAN_GATES_ENABLED) --------------------------


@pytest.mark.asyncio
async def test_plan_gates_disabled_unlocks_starter_org(client, db_session, monkeypatch):
    """The single testing escape hatch — every plan-gate reads
    get_effective_plan, so flipping this one setting must unlock a Starter
    org everywhere at once (checked here via the subscription endpoint,
    the same mechanism every other gate relies on).
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["plan"]["code"] == "professional"


@pytest.mark.asyncio
async def test_plan_gates_enabled_by_default(client, db_session):
    """Default (no override) must stay on — this is the production-safety case."""
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.get(
        "/api/v1/billing/subscription",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["plan"]["code"] == "starter"


# --- Cancel subscription -------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_subscription_rejects_plain_member(client, db_session):
    from app.modules.users.models import Organization

    token, user = await register_and_promote(
        client, db_session, "EMPLOYER", org_role=OrganizationRole.MEMBER.value
    )
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(db_session, organization, plan_code="professional")

    response = await client.post(
        "/api/v1/billing/subscription/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cancel_subscription_no_active_subscription_returns_400(
    client, db_session
):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.post(
        "/api/v1/billing/subscription/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "NO_ACTIVE_SUBSCRIPTION"


@pytest.mark.asyncio
async def test_cancel_subscription_schedules_cancellation_at_period_end(
    client, db_session
):
    """Cancelling doesn't yank access immediately — plan stays professional
    and the period end is unchanged, just flagged not to renew.
    """
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session, organization, plan_code="professional"
    )

    response = await client.post(
        "/api/v1/billing/subscription/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["code"] == "professional"
    assert body["cancel_at_period_end"] is True

    await db_session.refresh(subscription)
    assert subscription.cancel_at_period_end is True
    assert subscription.canceled_at is not None
    assert subscription.status == "ACTIVE"


@pytest.mark.asyncio
async def test_cancel_subscription_is_idempotent(client, db_session):
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    await make_subscription_for(db_session, organization, plan_code="professional")

    first = await client.post(
        "/api/v1/billing/subscription/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    second = await client.post(
        "/api/v1/billing/subscription/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["cancel_at_period_end"] is True


# --- Expiry sweep (BillingService.expire_lapsed_subscriptions) ----------


@pytest.mark.asyncio
async def test_expire_lapsed_subscriptions_drops_canceled_org_to_starter(
    client, db_session
):
    from datetime import UTC, datetime, timedelta

    from app.modules.billing.service import BillingService
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        current_period_end=datetime.now(UTC) - timedelta(days=1),
        cancel_at_period_end=True,
    )

    service = BillingService(db_session)
    expired_count = await service.expire_lapsed_subscriptions()
    await db_session.commit()

    assert expired_count == 1
    await db_session.refresh(subscription)
    assert subscription.status == "EXPIRED"

    plan = await service.get_effective_plan(user.organization_id)
    assert plan.code == "starter"


@pytest.mark.asyncio
async def test_expire_lapsed_subscriptions_ignores_active_renewal_window(
    client, db_session
):
    """A subscription still within its paid period, even if flagged to
    cancel, must not be touched yet — access continues until period end.
    """
    from app.modules.billing.service import BillingService
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        cancel_at_period_end=True,
    )

    service = BillingService(db_session)
    expired_count = await service.expire_lapsed_subscriptions()
    await db_session.commit()

    assert expired_count == 0
    await db_session.refresh(subscription)
    assert subscription.status == "ACTIVE"


@pytest.mark.asyncio
async def test_expire_lapsed_subscriptions_ignores_non_canceled_lapsed_org(
    client, db_session
):
    """An org that never canceled but whose period_end has passed is left
    alone by this sweep — that's the separate recurring-billing gap, not
    this method's job (see docs/... and BillingService docstring).
    """
    from datetime import UTC, datetime, timedelta

    from app.modules.billing.service import BillingService
    from app.modules.users.models import Organization

    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    result = await db_session.execute(
        select(Organization).where(Organization.id == user.organization_id)
    )
    organization = result.scalar_one()
    subscription = await make_subscription_for(
        db_session,
        organization,
        plan_code="professional",
        current_period_end=datetime.now(UTC) - timedelta(days=1),
    )

    service = BillingService(db_session)
    expired_count = await service.expire_lapsed_subscriptions()
    await db_session.commit()

    assert expired_count == 0
    await db_session.refresh(subscription)
    assert subscription.status == "ACTIVE"
