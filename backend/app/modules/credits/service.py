"""Business logic for the employer credits ledger."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientCreditsException
from app.modules.credits.repository import (
    INTERVIEW_CHARGE,
    INTERVIEW_REFUND,
    CreditsRepository,
)


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

    # ------------------------------------------------------------------
    # AI interviews. One rule: an interview is PAID when its charges outnumber
    # its refunds. See docs/11_PRICING_MODEL.md.
    # ------------------------------------------------------------------

    async def has_outstanding_interview_charge(
        self, organization_id: uuid.UUID, interview_id: uuid.UUID
    ) -> bool:
        """Whether this interview is paid (charged and not refunded)."""
        return await self._repo.has_outstanding_interview_charge(
            organization_id, interview_id
        )

    async def charge_interview(
        self, organization_id: uuid.UUID, interview_id: uuid.UUID, amount: int
    ) -> bool:
        """Take ``amount`` credits for an interview, unless it is already paid.

        Returns True when credits were taken now, False when nothing was taken (a
        price of 0, or the interview is already paid, as on a resend).

        The organization's balance row is locked first, so everything touching
        this organization's credits runs one at a time: "is it already paid?" and
        "take the credits" cannot be split by another request.

        Raises:
            InsufficientCreditsException: If the balance is lower than ``amount``.

        Does NOT commit: the caller owns the transaction.
        """
        if amount <= 0:
            return False
        balance = await self._repo.get_or_create_balance(organization_id, lock=True)
        if await self._repo.has_outstanding_interview_charge(
            organization_id, interview_id
        ):
            return False
        if balance.balance < amount:
            raise InsufficientCreditsException(
                message=(
                    f"Not enough credits. An AI interview costs {amount} credits "
                    f"and your balance is {balance.balance}."
                )
            )
        await self._repo.apply_delta(
            organization_id, -amount, INTERVIEW_CHARGE, interview_id
        )
        return True

    async def refund_interview(
        self, organization_id: uuid.UUID, interview_id: uuid.UUID
    ) -> int:
        """Give back what an interview was charged, once. Returns the credits
        returned, or 0 when there was nothing to return (never charged, or
        already refunded).

        The amount is what was actually charged, not today's price. Does NOT
        commit: the caller owns the transaction.
        """
        await self._repo.get_or_create_balance(organization_id, lock=True)
        if not await self._repo.has_outstanding_interview_charge(
            organization_id, interview_id
        ):
            return 0
        amount = await self._repo.latest_interview_charge(organization_id, interview_id)
        if not amount:
            return 0
        await self._repo.apply_delta(
            organization_id, amount, INTERVIEW_REFUND, interview_id
        )
        return amount

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
