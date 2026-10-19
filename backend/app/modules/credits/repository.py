"""Data-access layer for the employer credits ledger."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.credits.models import CreditTransaction, EmployerCredits

# Ledger reasons for AI interviews. The reference_id is the interview's id.
INTERVIEW_CHARGE = "interview_charge"
INTERVIEW_REFUND = "interview_refund"

# Ledger reasons for a plan's monthly credits. The reference_id of a deposit is the
# id of the payment that earned it, which is what makes a deposit happen once.
PLAN_ALLOWANCE = "plan_allowance"
PLAN_ALLOWANCE_EXPIRY = "plan_allowance_expiry"


class CreditsRepository:
    """Queries and mutations for EmployerCredits and CreditTransaction."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_balance(
        self, employer_id: uuid.UUID, *, lock: bool = False
    ) -> EmployerCredits:
        """Get or create an EmployerCredits row for the given employer.

        With ``lock=True`` the row is locked (``SELECT ... FOR UPDATE``) until the
        caller's transaction ends, so two requests changing the same balance at
        the same moment run one after the other instead of both reading the same
        number. Use it for anything that is about to change the balance.
        """
        stmt = select(EmployerCredits).where(EmployerCredits.employer_id == employer_id)
        if lock:
            # populate_existing: never trust a copy loaded earlier in this
            # session; the number in the database now is the one that counts.
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        result = await self._db.execute(stmt)
        balance = result.scalar_one_or_none()
        if balance is None:
            try:
                # A savepoint, so losing the race below does not poison the
                # caller's transaction.
                async with self._db.begin_nested():
                    balance = EmployerCredits(employer_id=employer_id)
                    self._db.add(balance)
                    await self._db.flush()
            except IntegrityError:
                # Another request created the row first (one row per
                # organization): read, and lock, theirs.
                result = await self._db.execute(stmt)
                balance = result.scalar_one()
        return balance

    async def get_balance(self, employer_id: uuid.UUID) -> int:
        """Everything the organization can spend: plan credits plus bought credits."""
        row = await self.get_or_create_balance(employer_id)
        return row.plan_balance + row.balance

    async def has_outstanding_interview_charge(
        self, organization_id: uuid.UUID, interview_id: uuid.UUID
    ) -> bool:
        """Whether an interview is paid: its charges outnumber its refunds."""
        counts = (
            await self._db.execute(
                select(CreditTransaction.reason, func.count())
                .where(
                    CreditTransaction.employer_id == organization_id,
                    CreditTransaction.reference_id == interview_id,
                    CreditTransaction.reason.in_([INTERVIEW_CHARGE, INTERVIEW_REFUND]),
                )
                .group_by(CreditTransaction.reason)
            )
        ).all()
        by_reason = dict(counts)
        return by_reason.get(INTERVIEW_CHARGE, 0) > by_reason.get(INTERVIEW_REFUND, 0)

    async def latest_interview_charge(
        self, organization_id: uuid.UUID, interview_id: uuid.UUID
    ) -> CreditTransaction | None:
        """The interview's most recent charge row (what it took, and how much of
        that came from plan credits), or None."""
        return (
            await self._db.execute(
                select(CreditTransaction)
                .where(
                    CreditTransaction.employer_id == organization_id,
                    CreditTransaction.reference_id == interview_id,
                    CreditTransaction.reason == INTERVIEW_CHARGE,
                )
                .order_by(CreditTransaction.created_at.desc())
                .limit(1)
                # Re-read the row: a row written earlier in this session holds the
                # insert-time expression, not the stored timestamp.
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

    async def latest_plan_reset_at(
        self, organization_id: uuid.UUID
    ) -> datetime | None:
        """When the plan credits were last replaced or wiped, or None if never.

        A refund uses this: plan credits taken before that moment no longer exist
        to be given back to.
        """
        return (
            await self._db.execute(
                select(func.max(CreditTransaction.created_at)).where(
                    CreditTransaction.employer_id == organization_id,
                    CreditTransaction.reason.in_(
                        [PLAN_ALLOWANCE, PLAN_ALLOWANCE_EXPIRY]
                    ),
                )
            )
        ).scalar_one_or_none()

    async def has_plan_allowance_for(
        self, organization_id: uuid.UUID, payment_id: uuid.UUID
    ) -> bool:
        """Whether the plan credits for this payment were already deposited."""
        found = (
            await self._db.execute(
                select(CreditTransaction.id)
                .where(
                    CreditTransaction.employer_id == organization_id,
                    CreditTransaction.reason == PLAN_ALLOWANCE,
                    CreditTransaction.reference_id == payment_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        return found is not None

    async def apply_delta(
        self,
        employer_id: uuid.UUID,
        delta: int,
        reason: str,
        reference_id: uuid.UUID | None = None,
        plan_portion: int | None = None,
    ) -> EmployerCredits:
        """
        Apply a signed delta to an employer's credits and record the transaction.

        If delta is positive, credits are added.
        If delta is negative, credits are subtracted.

        An organization holds two pots: plan credits (``plan_balance``) and bought
        credits (``balance``). ``plan_portion`` says how much of the delta moves the
        plan pot; the rest moves the bought pot. Left as None it is worked out: a
        spend takes plan credits first, and anything coming in is bought credits.
        Refunds, deposits and wipes pass it explicitly.

        Raises ValidationException if either pot would go negative.
        Does NOT commit — caller owns the transaction.
        """
        balance = await self.get_or_create_balance(employer_id, lock=True)
        if plan_portion is None:
            plan_portion = min(balance.plan_balance, -delta) if delta < 0 else 0
        if not 0 <= plan_portion <= abs(delta):
            raise ValueError("plan_portion must be between 0 and the size of the delta")

        plan_change = plan_portion if delta > 0 else -plan_portion
        new_plan_balance = balance.plan_balance + plan_change
        new_balance = balance.balance + (delta - plan_change)
        if new_plan_balance < 0 or new_balance < 0:
            raise ValidationException(
                "Insufficient credits: "
                f"balance={balance.plan_balance + balance.balance}, "
                f"requested debit={abs(delta)}"
            )

        balance.plan_balance = new_plan_balance
        balance.balance = new_balance
        transaction = CreditTransaction(
            employer_id=employer_id,
            delta=delta,
            reason=reason,
            reference_id=reference_id,
            plan_portion=plan_portion,
            # The moment of the insert, not the transaction's start (the column's
            # default): rows are written under the balance lock, so this puts them
            # in the order the changes really happened, which refunds rely on to
            # tell whether the plan credits were reset after a charge.
            created_at=func.clock_timestamp(),
        )
        self._db.add(transaction)
        await self._db.flush()
        return balance
