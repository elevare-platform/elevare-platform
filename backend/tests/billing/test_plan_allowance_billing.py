"""A paid plan's monthly credits arrive with the payment that earns them.

The first payment and every renewal replace the organization's plan credits with a
fresh allowance, once per payment; an ended subscription loses what is left; bought
credits are never touched."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.billing.models import Payment, Plan
from app.modules.billing.providers.base import TransactionResult
from app.modules.billing.providers.paystack import PaystackAdapter
from app.modules.billing.service import BillingService
from app.modules.credits.service import CreditsService
from tests.conftest import (
    make_employer,
    make_organization_for,
    make_subscription_for,
)

VERIFY = "app.modules.billing.providers.paystack.PaystackAdapter.verify_transaction"


async def _plan(db_session, code) -> Plan:
    return (
        await db_session.execute(select(Plan).where(Plan.code == code))
    ).scalar_one()


async def _org(db_session, **subscription_overrides):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    subscription = await make_subscription_for(
        db_session, organization, **subscription_overrides
    )
    return organization, subscription


async def _pots(db_session, organization):
    balances = await CreditsService(db_session).get_balances(organization.id)
    return balances["plan_credits"], balances["purchased_credits"]


def _verified(amount_kobo):
    return TransactionResult(
        reference="ref",
        status="success",
        amount_kobo=amount_kobo,
        currency="NGN",
        paid_at=datetime.now(UTC),
    )


async def _pending_subscription_payment(db_session, organization, plan, purpose):
    payment = Payment(
        organization_id=organization.id,
        plan_id=plan.id,
        purpose=purpose,
        amount_kobo=plan.price_kobo,
        currency=plan.currency,
        status="PENDING",
        provider="PAYSTACK",
        provider_reference=f"PSK_allowance_{uuid4().hex}",
    )
    db_session.add(payment)
    await db_session.flush()
    return payment


@pytest.mark.asyncio
async def test_professional_includes_credits(db_session):
    """Guards the seeded number the whole feature rests on (migration p22_0020)."""
    assert (await _plan(db_session, "professional")).included_credits == 40
    assert not (await _plan(db_session, "starter")).included_credits


@pytest.mark.asyncio
async def test_a_first_payment_deposits_the_plans_credits(db_session):
    plan = await _plan(db_session, "professional")
    organization, _ = await _org(db_session)
    payment = await _pending_subscription_payment(
        db_session, organization, plan, "SUBSCRIPTION_INITIAL"
    )

    await BillingService(db_session)._finalize_verified_payment(
        payment, _verified(plan.price_kobo)
    )

    assert await _pots(db_session, organization) == (plan.included_credits, 0)


@pytest.mark.asyncio
async def test_the_same_payment_delivered_twice_deposits_once(db_session):
    plan = await _plan(db_session, "professional")
    organization, _ = await _org(db_session)
    payment = await _pending_subscription_payment(
        db_session, organization, plan, "SUBSCRIPTION_INITIAL"
    )
    service = BillingService(db_session)
    await service._finalize_verified_payment(payment, _verified(plan.price_kobo))
    await CreditsService(db_session).charge_interview(organization.id, uuid4(), 10)

    await service._finalize_verified_payment(payment, _verified(plan.price_kobo))

    # Still the allowance minus the interview: the second delivery added nothing.
    assert await _pots(db_session, organization) == (plan.included_credits - 10, 0)


@pytest.mark.asyncio
async def test_a_renewal_replaces_what_was_left_with_a_fresh_allowance(db_session):
    plan = await _plan(db_session, "professional")
    customer = f"CUS_allowance_{uuid4().hex[:8]}"
    organization, _ = await _org(db_session, provider_customer_code=customer)
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 10)  # bought credits
    await credits.reset_plan_allowance(organization.id, plan.included_credits, uuid4())
    await credits.charge_interview(organization.id, uuid4(), 25)  # 15 plan left

    reference = f"PSK_allowance_{uuid4().hex}"
    renewal = PaystackAdapter("unused").parse_webhook_event(
        json.dumps(
            {
                "event": "charge.success",
                "data": {
                    "reference": reference,
                    "plan": {"plan_code": "PLN_professional"},
                    "customer": {"customer_code": customer},
                },
            }
        ).encode()
    )
    with patch(VERIFY, return_value=_verified(plan.price_kobo)):
        await BillingService(db_session)._handle_possible_renewal_charge(renewal)

    # A fresh allowance (not 15 + 40), and the bought credits untouched.
    assert await _pots(db_session, organization) == (plan.included_credits, 10)


@pytest.mark.asyncio
async def test_activating_a_plan_without_a_payment_deposits_nothing(db_session):
    starter = await _plan(db_session, "starter")
    organization, _ = await _org(db_session)

    await BillingService(db_session)._activate_subscription(organization.id, starter)

    assert await _pots(db_session, organization) == (0, 0)


@pytest.mark.asyncio
async def test_a_payment_for_a_plan_that_includes_no_credits_deposits_nothing(
    db_session,
):
    enterprise = await _plan(db_session, "enterprise")
    organization, _ = await _org(db_session, plan_code="enterprise")
    payment = await _pending_subscription_payment(
        db_session, organization, enterprise, "SUBSCRIPTION_RENEWAL"
    )

    await BillingService(db_session)._finalize_verified_payment(
        payment, _verified(enterprise.price_kobo)
    )

    assert await _pots(db_session, organization) == (0, 0)


@pytest.mark.asyncio
async def test_a_lapsed_subscription_loses_its_plan_credits_and_keeps_bought_ones(
    db_session,
):
    plan = await _plan(db_session, "professional")
    now = datetime.now(UTC)
    organization, subscription = await _org(
        db_session,
        cancel_at_period_end=True,
        current_period_start=now - timedelta(days=31),
        current_period_end=now - timedelta(days=1),
    )
    credits = CreditsService(db_session)
    await credits.grant(organization.id, 10)
    await credits.reset_plan_allowance(organization.id, plan.included_credits, uuid4())

    expired = await BillingService(db_session).expire_lapsed_subscriptions()

    assert expired >= 1
    assert subscription.status == "EXPIRED"
    assert await _pots(db_session, organization) == (0, 10)
