"""Celery tasks for the billing module — stale-payment reconciliation.

Mirrors ingestion/tasks.py's reap_stale_import_runs_task shape: one
periodic sweep, its own engine, disposed in a finally block. No per-row
Celery dispatch — verify_transaction is one cheap HTTP call per stale
payment, simple enough to just loop through inline within a single run.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.celery_app import celery
from app.core.config import settings
from app.modules.billing.repository import BillingRepository
from app.modules.billing.service import BillingService

logger = logging.getLogger(__name__)

# How long a payment can sit PENDING before we actively re-check it with
# Paystack — long enough that a customer still mid-checkout isn't falsely
# flagged, short enough to catch a lost webhook promptly.
STALE_PENDING_THRESHOLD = timedelta(minutes=30)


@celery.task(time_limit=60 * 5, soft_time_limit=60 * 4)
def replay_unprocessed_webhooks_task():
    """Celery Beat task — retries payment webhooks that were recorded but never
    processed (a renewal whose confirmation call timed out, a restart between
    recording and processing). See BillingService.replay_unprocessed_webhooks.

    The reconcile task below covers payments WE started (top-ups, a first
    charge); a renewal is started by Paystack, so there is no pending payment to
    reconcile and this replay is the only thing that recovers a failed one.
    """
    asyncio.run(_run_replay_async())


async def _run_replay_async() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            processed = await BillingService(db).replay_unprocessed_webhooks()
            if processed:
                logger.info(
                    "replay_unprocessed_webhooks: processed %d event(s)", processed
                )
    finally:
        await engine.dispose()


@celery.task(time_limit=60 * 5, soft_time_limit=60 * 4)
def reconcile_pending_payments_task():
    """Celery Beat task — actively resolves payments stuck PENDING.

    A webhook can be lost (network blip, Paystack outage, a redelivery
    window that expires before it succeeds) with nothing else in the
    system ever revisiting that payment again. This sweep is the backstop:
    ask Paystack directly for the current state of anything that's been
    PENDING too long, via the same BillingService.reconcile_pending_payment
    path (and the _finalize_verified_payment logic it shares with the
    webhook handler), so grant/notify/mark-failed behavior is identical
    regardless of which path resolves the payment.
    """
    asyncio.run(_run_reconcile_async())


async def _run_reconcile_async() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            repo = BillingRepository(db)
            cutoff = datetime.now(UTC) - STALE_PENDING_THRESHOLD
            stale_payments = await repo.list_stale_pending_payments(older_than=cutoff)
            if not stale_payments:
                return

            service = BillingService(db)
            resolved = 0
            for payment in stale_payments:
                try:
                    await service.reconcile_pending_payment(payment.id)
                    await db.commit()
                    resolved += 1
                except Exception:
                    # One payment failing to reconcile (e.g. a transient
                    # Paystack error) shouldn't abort the rest of the sweep.
                    await db.rollback()
                    logger.exception(
                        "reconcile_pending_payments: failed to reconcile payment %s",
                        payment.id,
                    )

            logger.info(
                "reconcile_pending_payments: checked %d stale payment(s), "
                "%d completed without error",
                len(stale_payments),
                resolved,
            )
    finally:
        await engine.dispose()


@celery.task(time_limit=60 * 5, soft_time_limit=60 * 4)
def expire_lapsed_subscriptions_task():
    """Celery Beat task — drops subscriptions past their period end back to
    Starter, for any org that canceled via BillingService.cancel_subscription.

    Nothing else in the system re-charges a subscription at renewal yet
    (see docs/... recurring-billing gap), so this only ever acts on
    cancellations a user explicitly requested.
    """
    asyncio.run(_run_expire_async())


@celery.task(time_limit=60 * 5, soft_time_limit=60 * 4)
def disable_expired_starter_jobs_task():
    """Celery Beat task, hourly: switches off the live jobs of Starter companies that have
    run for 30 days (the other half of "10 applicants or 30 days, whichever comes first").
    Does nothing while plan gating is off. Safe to run twice: a job already switched off is
    no longer live, so it is not touched again."""
    asyncio.run(_run_disable_expired_jobs_async())


async def _run_disable_expired_jobs_async() -> None:
    from app.modules.jobs.disabling import disable_expired_starter_jobs

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            try:
                await disable_expired_starter_jobs(db)
            except Exception:
                await db.rollback()
                logger.exception("disable_expired_starter_jobs: sweep failed")
    finally:
        await engine.dispose()


async def _run_expire_async() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            service = BillingService(db)
            try:
                expired_count = await service.expire_lapsed_subscriptions()
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("expire_lapsed_subscriptions: sweep failed")
                return

            if expired_count:
                logger.info(
                    "expire_lapsed_subscriptions: expired %d subscription(s)",
                    expired_count,
                )
    finally:
        await engine.dispose()
