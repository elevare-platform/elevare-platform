"""The credit history an organization sees: its ledger rows in plain language.

The ledger (``credit_transactions``) records reasons meant for the system, such as
``admin_grant``. Here each row gets wording a customer understands, and what it was
for (the job), without changing what is stored.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.billing.models import Payment
from app.modules.credits.models import CreditTransaction
from app.modules.credits.repository import (
    INTERVIEW_CHARGE,
    INTERVIEW_REFUND,
    PLAN_ALLOWANCE,
    PLAN_ALLOWANCE_EXPIRY,
    CreditsRepository,
)
from app.modules.credits.schemas import CreditHistoryItem, CreditHistoryPage
from app.modules.interviews.models import Interview
from app.modules.introductions.models import IntroductionRequest
from app.modules.jobs.models import Job

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# reason -> (kind, wording). A credit grant is split in two by whether a payment
# stands behind it (see _describe).
_WORDING = {
    "intro_request": ("introduction", "Introduction requested"),
    "intro_refund": ("introduction_refund", "Introduction credit returned"),
    INTERVIEW_CHARGE: ("interview", "AI interview invite"),
    INTERVIEW_REFUND: ("interview_refund", "AI interview credits returned"),
    PLAN_ALLOWANCE: ("plan_credits", "Monthly plan credits"),
    PLAN_ALLOWANCE_EXPIRY: ("plan_credits_expired", "Unused plan credits expired"),
}


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    """An opaque bookmark for "everything older than this row"."""
    raw = f"{created_at.isoformat()}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at, row_id = raw.split("|")
        return datetime.fromisoformat(created_at), uuid.UUID(row_id)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationException("Invalid cursor", code="INVALID_CURSOR") from exc


class CreditHistoryService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = CreditsRepository(db)

    async def get_history(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> CreditHistoryPage:
        """A page of the organization's credit history, newest first."""
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        before = decode_cursor(cursor) if cursor else None
        # One more than will be shown, only to learn whether there is a next page.
        rows = await self._repo.list_history(organization_id, limit=limit + 1, before=before)
        has_more = len(rows) > limit
        rows = rows[:limit]

        jobs = await self._job_titles(rows)
        purchases = await self._purchase_payment_ids(rows)
        items = [
            self._describe(row, jobs.get(row.reference_id), row.reference_id in purchases)
            for row in rows
        ]
        next_cursor = (
            encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
        )
        return CreditHistoryPage(items=items, next_cursor=next_cursor)

    @staticmethod
    def _describe(
        row: CreditTransaction, job_title: str | None, is_purchase: bool
    ) -> CreditHistoryItem:
        if row.reason == "admin_grant":
            # Both a bought pack and a gift from Elevare are stored as a grant; a
            # pack is the one with a payment behind it.
            kind, description = (
                ("pack_purchase", "Credit pack purchased")
                if is_purchase
                else ("grant", "Credits added by Elevare")
            )
        else:
            kind, description = _WORDING.get(
                row.reason, ("other", row.reason.replace("_", " ").capitalize())
            )
        plan_change = row.plan_portion if row.delta > 0 else -row.plan_portion
        return CreditHistoryItem(
            id=row.id,
            created_at=row.created_at,
            kind=kind,
            description=description,
            detail=job_title,
            credits_change=row.delta,
            plan_credits_change=plan_change,
            purchased_credits_change=row.delta - plan_change,
        )

    async def _job_titles(self, rows: list[CreditTransaction]) -> dict[uuid.UUID, str]:
        """The job each interview or introduction row was for, by its reference id.
        Two queries for the whole page, not one per row."""
        interview_ids: list[uuid.UUID] = []
        introduction_ids: list[uuid.UUID] = []
        for row in rows:
            if row.reference_id is None:
                continue
            if row.reason in (INTERVIEW_CHARGE, INTERVIEW_REFUND):
                interview_ids.append(row.reference_id)
            elif row.reason in ("intro_request", "intro_refund"):
                introduction_ids.append(row.reference_id)

        titles: dict[uuid.UUID, str] = {}
        if interview_ids:
            found = await self._db.execute(
                select(Interview.id, Job.title)
                .join(Job, Job.id == Interview.job_id)
                .where(Interview.id.in_(interview_ids))
            )
            titles.update(dict(found.all()))
        if introduction_ids:
            found = await self._db.execute(
                select(IntroductionRequest.id, Job.title)
                .join(Job, Job.id == IntroductionRequest.job_id)
                .where(IntroductionRequest.id.in_(introduction_ids))
            )
            titles.update(dict(found.all()))
        return titles

    async def _purchase_payment_ids(
        self, rows: list[CreditTransaction]
    ) -> set[uuid.UUID]:
        """Which of the page's grants were paid for: their reference is a credit
        top-up payment."""
        candidates = [
            row.reference_id
            for row in rows
            if row.reason == "admin_grant" and row.reference_id is not None
        ]
        if not candidates:
            return set()
        found = await self._db.execute(
            select(Payment.id).where(
                Payment.id.in_(candidates), Payment.purpose == "CREDIT_TOPUP"
            )
        )
        return set(found.scalars().all())
