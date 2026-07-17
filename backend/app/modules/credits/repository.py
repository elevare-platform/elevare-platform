"""Data-access layer for the employer credits ledger."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.credits.models import CreditTransaction, EmployerCredits


class CreditsRepository:
    """Queries and mutations for EmployerCredits and CreditTransaction."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_or_create_balance(self, employer_id: uuid.UUID) -> EmployerCredits:
        """Get or create an EmployerCredits row for the given employer."""
        stmt = select(EmployerCredits).where(EmployerCredits.employer_id == employer_id)
        result = await self._db.execute(stmt)
        balance = result.scalar_one_or_none()
        if balance is None:
            balance = EmployerCredits(employer_id=employer_id)
            self._db.add(balance)
            await self._db.flush()
        return balance

    async def get_balance(self, employer_id: uuid.UUID) -> EmployerCredits:
        """Get an EmployerCredits row for the given employer."""
        row = await self.get_or_create_balance(employer_id)
        return row.balance

    async def apply_delta(
        self,
        employer_id: uuid.UUID,
        delta: int,
        reason: str,
        reference_id: uuid.UUID | None = None,
    ) -> EmployerCredits:
        """
        Apply a signed delta to an employer's balance and record the transaction.

        If delta is positive, credits are added.
        If delta is negative, credits are subtracted (caller must ensure sufficient balance).

        Raises ValueError if the resulting balance would go negative.
        Does NOT commit — caller owns the transaction.
        """
        balance = await self.get_or_create_balance(employer_id)
        new_balance = balance.balance + delta
        if new_balance < 0:
            raise ValidationException(
                f"Insufficient credits: balance={balance.balance}, requested debit={abs(delta)}"
            )

        balance.balance = new_balance
        transaction = CreditTransaction(
            employer_id=employer_id,
            delta=delta,
            reason=reason,
            reference_id=reference_id,
        )
        self._db.add(transaction)
        await self._db.flush()
        return balance
