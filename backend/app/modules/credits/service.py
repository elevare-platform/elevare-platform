"""Business logic for the employer credits ledger."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InsufficientCreditsException
from app.modules.credits.repository import (
    INTERVIEW_CHARGE,
    INTERVIEW_REFUND,
    INTRODUCTION_CREDIT_COST,
    PLAN_ALLOWANCE,
    PLAN_ALLOWANCE_EXPIRY,
    CreditsRepository,
)

logger = logging.getLogger(__name__)


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
        Get everything an employer can spend: plan credits plus bought credits.

        Returns: int — the current total
        """
        balance = await self._repo.get_balance(employer_id)
        return balance

    async def get_balances(self, employer_id: uuid.UUID) -> dict:
        """The two pots separately, and the total.

        ``plan_credits`` are included in the plan and replaced at each renewal;
        ``purchased_credits`` were bought or granted and never expire.
        """
        row = await self._repo.get_or_create_balance(employer_id)
        return {
            "total": row.plan_balance + row.balance,
            "plan_credits": row.plan_balance,
            "purchased_credits": row.balance,
        }

    async def grant(
        self,
        employer_id: uuid.UUID,
        amount: int,
        reference_id: uuid.UUID | None = None,
    ) -> int:
        """Add bought credits (a purchase or an admin grant). Returns the new total.

        Does NOT commit — caller owns the transaction.
        """
        balance = await self._repo.apply_delta(
            employer_id,
            delta=amount,
            reason="admin_grant",
            reference_id=reference_id,
        )
        return balance.plan_balance + balance.balance

    # ------------------------------------------------------------------
    # A plan's monthly credits. Replaced at each renewal, wiped when the
    # subscription lapses; bought credits are never touched. See
    # docs/11_PRICING_MODEL.md.
    # ------------------------------------------------------------------

    async def reset_plan_allowance(
        self, organization_id: uuid.UUID, credits: int, payment_id: uuid.UUID
    ) -> bool:
        """Replace the organization's plan credits with a fresh ``credits`` for
        the period this payment paid for. Returns False, changing nothing, when
        this payment already earned its credits (a retried webhook, the verify
        call and the replay sweep can all reach the same payment).

        What is left of the old plan credits is wiped first, as its own ledger row.
        Both rows are written under the balance lock, so the check, the wipe and
        the deposit cannot be split by another request.

        Does NOT commit: the caller owns the transaction.
        """
        if credits <= 0:
            return False
        balance = await self._repo.get_or_create_balance(organization_id, lock=True)
        if await self._repo.has_plan_allowance_for(organization_id, payment_id):
            return False
        await self._wipe_plan_credits(organization_id, balance.plan_balance)
        await self._repo.apply_delta(
            organization_id,
            credits,
            PLAN_ALLOWANCE,
            payment_id,
            plan_portion=credits,
        )
        return True

    async def expire_plan_allowance(self, organization_id: uuid.UUID) -> int:
        """Wipe the organization's plan credits (its subscription has ended).
        Returns how many were wiped. Bought credits are kept.

        Does NOT commit: the caller owns the transaction.
        """
        balance = await self._repo.get_or_create_balance(organization_id, lock=True)
        remaining = balance.plan_balance
        await self._wipe_plan_credits(organization_id, remaining)
        return remaining

    async def _wipe_plan_credits(self, organization_id: uuid.UUID, remaining: int) -> None:
        """Write the wipe row, even when nothing is left (``remaining`` 0): it also
        marks when the plan credits were last reset, which refunds look at."""
        await self._repo.apply_delta(
            organization_id,
            -remaining,
            PLAN_ALLOWANCE_EXPIRY,
            plan_portion=remaining,
        )

    async def deduct(
        self,
        employer_id: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> int:
        """Deduct 1 credit, plan credits first. Returns the new total. Raises
        ValidationException if there are no credits.

        Does NOT commit — caller owns the transaction.
        """
        balance = await self._repo.apply_delta(
            employer_id,
            delta=-INTRODUCTION_CREDIT_COST,
            reason="intro_request",
            reference_id=reference_id,
        )
        return balance.plan_balance + balance.balance

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
        self,
        organization_id: uuid.UUID,
        interview_id: uuid.UUID,
        amount: int,
        *,
        again: bool = False,
    ) -> bool:
        """Take ``amount`` credits for an interview, unless it is already paid.

        Returns True when credits were taken now, False when nothing was taken (a
        price of 0, or the interview is already paid, as on a resend).

        ``again`` takes the credits even though the interview is paid: for a candidate
        who is let take a COMPLETED interview a second time, which is a new interview with
        its own cost. The interview then has two charges, so it counts as paid until both
        are refunded (see ``has_outstanding_interview_charge``).

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
        if not again and await self._repo.has_outstanding_interview_charge(
            organization_id, interview_id
        ):
            return False
        available = balance.plan_balance + balance.balance
        if available < amount:
            raise InsufficientCreditsException(
                message=(
                    f"Not enough credits. An interview costs {amount} credits "
                    f"and your balance is {available}."
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

        The amount is what was actually charged, not today's price. It goes back
        to the pots it came from: the plan part to plan credits, the rest to bought
        credits. If the plan credits were replaced or wiped since the charge, that
        plan part no longer has a pot to return to, so it comes back as bought
        credits (the customer is made whole, and the allowance never ends up above
        what the plan includes). Does NOT commit: the caller owns the transaction.
        """
        await self._repo.get_or_create_balance(organization_id, lock=True)
        if not await self._repo.has_outstanding_interview_charge(
            organization_id, interview_id
        ):
            return 0
        charge = await self._repo.latest_charge(
            organization_id, interview_id, INTERVIEW_CHARGE
        )
        if charge is None or charge.delta == 0:
            return 0
        amount = abs(charge.delta)
        plan_portion = await self._plan_part_still_returnable(organization_id, charge)
        await self._repo.apply_delta(
            organization_id,
            amount,
            INTERVIEW_REFUND,
            interview_id,
            plan_portion=plan_portion,
        )
        return amount

    async def refund(
        self,
        employer_id: uuid.UUID,
        reference_id: uuid.UUID | None = None,
    ) -> int:
        """Refund 1 credit (decline or expiry). Returns the new total.

        The credit goes back to the pot it was taken from, found through the
        introduction request's id (the charge is recorded with it). If the plan
        credits were replaced or wiped since, or the request was charged before
        charges carried an id, it comes back as a bought credit, which never
        expires.

        A request is refunded at most once: the expired link can be opened again,
        the employer's list can notice the expiry too, and a double click can send
        two declines at once, and each of those asks for a refund. Under the
        balance lock, a request that already has a refund gets nothing more.

        Does NOT commit — caller owns the transaction.
        """
        # Lock first, so "was the plan pot reset since the charge?" and "was it
        # already refunded?" are answered about the state the refund is applied to.
        balance = await self._repo.get_or_create_balance(employer_id, lock=True)
        if reference_id is not None and await self._repo.has_refund_for(
            employer_id, reference_id, "intro_refund"
        ):
            logger.info(
                "Introduction %s was already refunded; not refunding it again",
                reference_id,
            )
            return balance.plan_balance + balance.balance
        plan_portion = 0
        if reference_id is not None:
            charge = await self._repo.latest_charge(
                employer_id, reference_id, "intro_request"
            )
            if charge is not None:
                plan_portion = await self._plan_part_still_returnable(
                    employer_id, charge
                )
        row = await self._repo.apply_delta(
            employer_id=employer_id,
            delta=INTRODUCTION_CREDIT_COST,
            reason="intro_refund",
            reference_id=reference_id,
            plan_portion=plan_portion,
        )
        return row.plan_balance + row.balance

    async def _plan_part_still_returnable(
        self, organization_id: uuid.UUID, charge
    ) -> int:
        """How much of a charge's plan part can still go back to the plan credits:
        all of it, unless the plan credits were replaced or wiped since the charge
        (then they no longer exist to return to, and it goes to bought credits)."""
        last_reset = await self._repo.latest_plan_reset_at(organization_id)
        if last_reset is not None and last_reset > charge.created_at:
            return 0
        return charge.plan_portion
