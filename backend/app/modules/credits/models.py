"""SQLAlchemy ORM models for the employer credits ledger."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UUID, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.users.models import User


class EmployerCredits(BaseModel):
    """One row per employer - holds their current credit balance."""

    __tablename__ = "employer_credits"
    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="ck_employer_credits_balance_non_negative",
        ),
    )

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
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
    employer: Mapped[User] = relationship("User", back_populates="employer_credits")


class CreditTransaction(BaseModel):
    """Ledger of all credit changes for an employer."""

    __tablename__ = "credit_transactions"

    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
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

    employer: Mapped[User] = relationship(
        "User",
        foreign_keys=[employer_id],
        back_populates="credit_transactions",
    )
