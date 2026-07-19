"""Business logic for the employer credits ledger."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.credits.repository import CreditsRepository


class CreditsService:
    """
    Business logic for employer credits.
    - Provides a method to debit credits for a specific action (e.g. introduction request).
    - Wraps repository calls and commits the transaction after successful debit.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialise the service with a database session.
        """
        self._db = db
        self._repo = CreditsRepository(db)

    async def get_balance(self, employer_id: uuid.UUID):
        """
        Get the current credit balance for an employer.

        Returns: int — the current balance
        Raises: ValueError if the employer does not exist
        """
        balance = await self._repo.get_balance(employer_id)
        return balance

    async def grant(
        self,
        employer_id: uuid.UUID,
        amount: int,
        reference_id: uuid.UUID | None = None,
    ) -> int:
        """Add credits to an employer's balance. Returns new balance.

        Does NOT commit — caller owns the transaction.
        """
        balance = await self._repo.apply_delta(
            employer_id,
            delta=amount,
            reason="admin_grant",
            reference_id=reference_id,
        )
        return balance.balance

    async def deduct(
        self,
        employer_id: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> int:
        """Deduct 1 credit. Raises ValueError if balance is 0.

        Does NOT commit — caller owns the transaction.
        """
        balance = await self._repo.apply_delta(
            employer_id,
            delta=-1,
            reason="intro_request",
            reference_id=reference_id,
        )
        return balance.balance

    async def refund(
        self,
        employer_id: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> int:
        """Refund 1 credit (decline or expiry). Returns new balance.

        Does NOT commit — caller owns the transaction.
        """
        row = await self._repo.apply_delta(
            employer_id=employer_id,
            delta=1,
            reason="intro_refund",
            reference_id=reference_id,
        )
        return row.balance
