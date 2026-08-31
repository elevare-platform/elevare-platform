"""SQLAlchemy ORM models for the employer credits ledger."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.users.models import Organization


class EmployerCredits(BaseModel):
    """One row per organization - holds its current shared credit balance.

    Keyed to `organizations.id`, not `users.id` — credits are a company
    wallet shared by every member of an Organization (see
    docs/subscription-payment-architecture-review.md finding #7). The
    `employer_id` column name is kept as-is even though it now points at
    an Organization: every caller already treats it as an opaque FK
    target, so renaming it would be pure churn.
    """

    __tablename__ = "employer_credits"
    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="ck_employer_credits_balance_non_negative",
        ),
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    balance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Relationship
    organization: Mapped[Organization] = relationship(
        "Organization", back_populates="employer_credits"
    )


class CreditTransaction(BaseModel):
    """Ledger of all credit changes for an organization's shared wallet."""

    __tablename__ = "credit_transactions"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # positive = credit in (grant, refund), negative = debit (intro_request)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # admin_grant | intro_request | intro_refund
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # introduction_request.id or admin action id

    organization: Mapped[Organization] = relationship(
        "Organization",
        foreign_keys=[employer_id],
        back_populates="credit_transactions",
    )
