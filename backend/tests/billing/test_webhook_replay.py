"""A payment webhook that failed to process is retried, not forgotten.

Before this, an event was saved as "received" before it was processed, a failure
left it unprocessed while answering 200 (so Paystack never resent it), and a
redelivery was ignored as a duplicate. A customer whose renewal webhook failed
once paid, but never had their subscription extended, and was later dropped to
Starter.

These tests use real committed sessions (not the usual rolled-back one): a failed
event is rolled back by the handler, which would also wipe an ordinary test's
setup data. Everything they create is removed afterwards."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import event, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery
from app.modules.billing.models import Payment, Subscription, WebhookEvent
from app.modules.billing.providers.base import TransactionResult
from app.modules.billing.providers.paystack import (
    PaystackAdapter,
    PaystackVerificationError,
)
from app.modules.billing.repository import BillingRepository
from app.modules.billing.service import BillingService
from tests.conftest import (
    make_employer,
    make_organization_for,
    make_subscription_for,
    test_engine,
)

CUSTOMER = "CUS_replay_test"
VERIFY = "app.modules.billing.providers.paystack.PaystackAdapter.verify_transaction"
SIGNATURE = (
    "app.modules.billing.providers.paystack.PaystackAdapter.verify_webhook_signature"
)


def _session() -> AsyncSession:
    return AsyncSession(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def subscriber():
    """A committed organization with a Professional subscription tied to a Paystack
    customer code (what a renewal charge is matched by). Yields (org_id, subscription
    id, period end before any renewal)."""
    async with _session() as db:
        employer = make_employer()
        db.add(employer)
        await db.flush()
        organization = await make_organization_for(db, employer)
        subscription = await make_subscription_for(
            db, organization, plan_code="professional", provider_customer_code=CUSTOMER
        )
        await db.commit()
        ids = (organization.id, subscription.id, subscription.current_period_end)
        user_id = employer.id

    yield ids

    async with _session() as db:
        await db.execute(
            text("DELETE FROM payments WHERE organization_id = :o"), {"o": ids[0]}
        )
        await db.execute(
            text(
                "DELETE FROM webhook_events WHERE provider_event_id LIKE 'PSK_replay_%'"
            )
        )
        await db.execute(
            text("UPDATE users SET organization_id = NULL WHERE id = :u"),
            {"u": user_id},
        )
        await db.execute(text("DELETE FROM organizations WHERE id = :o"), {"o": ids[0]})
        await db.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
        await db.commit()


def _renewal(reference):
    return {
        "event": "charge.success",
        "data": {
            "reference": reference,
            "plan": {"plan_code": "PLN_professional"},
            "customer": {"customer_code": CUSTOMER},
        },
    }


def _paid(reference):
    return TransactionResult(
        reference=reference,
        status="success",
        amount_kobo=4_500_000,
        currency="NGN",
        paid_at=None,
    )


async def _record(
    body, *, age=timedelta(minutes=30), error="Paystack was down", processed=False
):
    """Store a webhook event as the handler would have left it after a failure."""
    parsed = PaystackAdapter("unused").parse_webhook_event(json.dumps(body).encode())
    async with _session() as db:
        recorded = await BillingRepository(db).record_webhook_event(
            provider="PAYSTACK",
            provider_event_id=parsed.provider_event_id,
            event_type=parsed.event_type,
            payload=parsed.payload,
        )
        recorded.processing_error = error
        if processed:
            recorded.processed_at = datetime.now(UTC)
        await db.flush()
        stamp = datetime.now(UTC) - age
        await db.execute(
            update(WebhookEvent)
            .where(WebhookEvent.id == recorded.id)
            .values(created_at=stamp, updated_at=stamp)
        )
        await db.commit()
    return parsed.provider_event_id


async def _stored(provider_event_id) -> WebhookEvent:
    async with _session() as db:
        return (
            await db.execute(
                select(WebhookEvent).where(
                    WebhookEvent.provider_event_id == provider_event_id
                )
            )
        ).scalar_one()


async def _payments(reference) -> list[Payment]:
    async with _session() as db:
        result = await db.execute(
            select(Payment).where(Payment.provider_reference == reference)
        )
        return list(result.scalars().all())


async def _period_end(subscription_id):
    async with _session() as db:
        return (
            await db.execute(
                select(Subscription.current_period_end).where(
                    Subscription.id == subscription_id
                )
            )
        ).scalar_one()


async def _replay(**kwargs) -> int:
    async with _session() as db:
        return await BillingService(db).replay_unprocessed_webhooks(**kwargs)


async def _deliver(body):
    """A webhook arriving over HTTP: the signature is accepted."""
    async with _session() as db:
        with patch(SIGNATURE, return_value=True):
            await BillingService(db).handle_webhook(
                "paystack", json.dumps(body).encode(), {"x-paystack-signature": "fake"}
            )


# ── The sweep ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_failed_renewal_is_replayed_and_the_subscription_extended(subscriber):
    _org, subscription_id, original_end = subscriber
    event_id = await _record(_renewal("PSK_replay_1"))

    with patch(VERIFY, AsyncMock(return_value=_paid("PSK_replay_1"))):
        processed = await _replay()

    assert processed == 1
    payments = await _payments("PSK_replay_1")
    assert [p.purpose for p in payments] == ["SUBSCRIPTION_RENEWAL"]
    assert await _period_end(subscription_id) > original_end
    stored = await _stored(event_id)
    assert stored.processed_at is not None
    assert stored.processing_error is None


@pytest.mark.asyncio
async def test_an_event_nothing_ever_tried_to_process_is_replayed_too(subscriber):
    """The worker died after recording the event and before processing it."""
    await _record(_renewal("PSK_replay_2"), error=None)

    with patch(VERIFY, AsyncMock(return_value=_paid("PSK_replay_2"))):
        assert await _replay() == 1

    assert len(await _payments("PSK_replay_2")) == 1


@pytest.mark.asyncio
async def test_a_processed_event_is_never_replayed(subscriber):
    await _record(_renewal("PSK_replay_3"), processed=True, error=None)
    verify = AsyncMock(return_value=_paid("PSK_replay_3"))

    with patch(VERIFY, verify):
        assert await _replay() == 0

    verify.assert_not_awaited()
    assert await _payments("PSK_replay_3") == []


@pytest.mark.asyncio
async def test_an_event_that_just_arrived_is_left_to_its_own_delivery(subscriber):
    """The sweep must never race the first delivery that is still processing it."""
    await _record(_renewal("PSK_replay_4"), age=timedelta(minutes=1), error=None)
    verify = AsyncMock(return_value=_paid("PSK_replay_4"))

    with patch(VERIFY, verify):
        assert await _replay() == 0

    verify.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_replay_that_fails_again_keeps_the_event_and_waits_before_retrying(
    subscriber,
):
    event_id = await _record(_renewal("PSK_replay_5"))
    verify = AsyncMock(side_effect=PaystackVerificationError("still down"))

    with patch(VERIFY, verify):
        assert await _replay() == 0
        stored = await _stored(event_id)
        assert stored.processed_at is None
        assert "still down" in stored.processing_error
        # Straight away again: the last attempt was moments ago, so it waits.
        assert await _replay() == 0

    assert verify.await_count == 1
    assert await _payments("PSK_replay_5") == []


@pytest.mark.asyncio
async def test_after_three_days_the_sweep_gives_up_on_an_event(subscriber):
    event_id = await _record(_renewal("PSK_replay_6"), age=timedelta(days=4))
    verify = AsyncMock(return_value=_paid("PSK_replay_6"))

    with patch(VERIFY, verify):
        assert await _replay() == 0

    verify.assert_not_awaited()
    assert (await _stored(event_id)).processed_at is None


@pytest.mark.asyncio
async def test_giving_up_is_reported_loudly_once_it_happens(subscriber, caplog):
    event_id = await _record(
        _renewal("PSK_replay_7"), age=timedelta(days=3, minutes=10)
    )

    with caplog.at_level(logging.ERROR):
        with patch(VERIFY, AsyncMock(return_value=_paid("PSK_replay_7"))):
            assert await _replay() == 0

    assert any(event_id in record.getMessage() for record in caplog.records)


@pytest.mark.asyncio
async def test_one_bad_event_does_not_block_the_others(subscriber):
    await _record(_renewal("PSK_replay_8"), age=timedelta(minutes=40))
    good_id = await _record(_renewal("PSK_replay_9"), age=timedelta(minutes=30))

    async def verify(reference):
        if reference == "PSK_replay_8":
            raise PaystackVerificationError("down for this one")
        return _paid(reference)

    with patch(VERIFY, AsyncMock(side_effect=verify)):
        processed = await _replay()

    assert processed == 1
    assert (await _stored(good_id)).processed_at is not None
    assert len(await _payments("PSK_replay_9")) == 1


@pytest.mark.asyncio
async def test_the_batch_is_bounded_and_the_rest_waits_for_the_next_sweep(subscriber):
    await _record(_renewal("PSK_replay_10"), age=timedelta(minutes=40))
    await _record(_renewal("PSK_replay_11"), age=timedelta(minutes=30))

    with patch(VERIFY, AsyncMock(side_effect=lambda ref: _paid(ref))):
        first = await _replay(limit=1)
        second = await _replay(limit=1)

    assert (first, second) == (1, 1)
    assert len(await _payments("PSK_replay_10")) == 1
    assert len(await _payments("PSK_replay_11")) == 1


@pytest.mark.asyncio
async def test_an_event_nothing_acts_on_is_still_marked_processed(subscriber):
    """Event types with no handler are logged for visibility; replaying must close
    them, not leave them to be retried for three days."""
    event_id = await _record(
        {"event": "subscription.disable", "data": {"subscription_code": "SUB_replay_x"}}
    )
    # The id helper in the test builds PSK_replay_ ids only for charges; record
    # the cleanup-friendly id by hand.
    async with _session() as db:
        await db.execute(
            text(
                "UPDATE webhook_events SET provider_event_id = 'PSK_replay_noop:subscription.disable' "
                "WHERE provider_event_id = :old"
            ),
            {"old": event_id},
        )
        await db.commit()

    assert await _replay() == 1
    noop = await _stored("PSK_replay_noop:subscription.disable")
    assert noop.processed_at is not None


@pytest.mark.asyncio
async def test_the_sweep_locks_rows_so_two_sweeps_do_not_collide(subscriber):
    await _record(_renewal("PSK_replay_12"))
    statements: list[str] = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(test_engine.sync_engine, "before_cursor_execute", capture)
    try:
        with patch(VERIFY, AsyncMock(return_value=_paid("PSK_replay_12"))):
            await _replay()
    finally:
        event.remove(test_engine.sync_engine, "before_cursor_execute", capture)

    assert any("FOR UPDATE SKIP LOCKED" in s for s in statements)


@pytest.mark.asyncio
async def test_two_sweeps_at_the_same_moment_process_an_event_once(subscriber):
    await _record(_renewal("PSK_replay_13"))

    async def slow_verify(reference):
        await asyncio.sleep(0.4)
        return _paid(reference)

    with patch(VERIFY, AsyncMock(side_effect=slow_verify)):
        results = await asyncio.gather(_replay(), _replay())

    assert sum(results) == 1
    assert len(await _payments("PSK_replay_13")) == 1


# ── A redelivery ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_redelivered_event_that_failed_the_first_time_is_processed(subscriber):
    """Paystack resends a webhook; the first delivery had failed. The duplicate
    check used to ignore it because the event was already on file."""
    body = _renewal("PSK_replay_14")

    with patch(VERIFY, AsyncMock(side_effect=PaystackVerificationError("down"))):
        await _deliver(body)
    assert await _payments("PSK_replay_14") == []

    with patch(VERIFY, AsyncMock(return_value=_paid("PSK_replay_14"))):
        await _deliver(body)

    assert len(await _payments("PSK_replay_14")) == 1
    assert (await _stored("PSK_replay_14:charge.success")).processed_at is not None


@pytest.mark.asyncio
async def test_a_redelivered_event_that_already_succeeded_does_nothing(subscriber):
    body = _renewal("PSK_replay_15")
    verify = AsyncMock(return_value=_paid("PSK_replay_15"))

    with patch(VERIFY, verify):
        await _deliver(body)
        await _deliver(body)

    assert verify.await_count == 1
    assert len(await _payments("PSK_replay_15")) == 1


# ── Scheduling ──────────────────────────────────────────────────────────────────


def test_the_sweep_is_scheduled_every_ten_minutes():
    import app.modules.billing.tasks  # noqa: F401  registers the task

    entry = celery.conf.beat_schedule["replay-unprocessed-webhooks"]

    assert entry["task"] == "app.modules.billing.tasks.replay_unprocessed_webhooks_task"
    assert entry["schedule"] == 60 * 10
    assert entry["task"] in celery.tasks
