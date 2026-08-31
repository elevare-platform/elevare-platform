"""One-off provisioning script: create a Paystack Plan for every paid Plan
in our catalog that doesn't have one yet, and store the resulting
`plan_code` on `plans.provider_plan_code`.

Run manually, once, wherever PAYSTACK_SECRET_KEY is the real live (or
test-mode) key — not part of any request path or migration. Safe to
re-run: it only touches plans where provider_plan_code is still null.

Usage (from inside the API container, with a real Paystack key set):
    python scripts/create_paystack_plans.py
"""

import asyncio

import app.main  # noqa: F401 — forces every module's models to register before querying
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.billing.models import Plan
from app.modules.billing.providers.paystack import PaystackAdapter

# Our Plan.interval values ("MONTHLY"/"ANNUAL") to what Paystack's
# /plan endpoint expects.
_INTERVAL_MAP = {"MONTHLY": "monthly", "ANNUAL": "annually"}


async def main() -> None:
    if not settings.paystack_secret_key:
        print("PAYSTACK_SECRET_KEY is not set — nothing to do.")
        return

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    adapter = PaystackAdapter(settings.paystack_secret_key)

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Plan).where(
                    Plan.price_kobo > 0, Plan.provider_plan_code.is_(None)
                )
            )
            plans = list(result.scalars().all())

            if not plans:
                print("Every paid plan already has a provider_plan_code. Nothing to do.")
                return

            for plan in plans:
                interval = _INTERVAL_MAP.get(plan.interval)
                if interval is None:
                    print(
                        f"Skipping {plan.code}: unrecognized interval {plan.interval!r}"
                    )
                    continue

                plan_code = await adapter.create_plan(
                    name=f"{plan.name} ({plan.interval.title()})",
                    amount_kobo=plan.price_kobo,
                    interval=interval,
                    currency=plan.currency,
                )
                plan.provider_plan_code = plan_code
                print(f"{plan.code} -> {plan_code}")

            await db.commit()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
