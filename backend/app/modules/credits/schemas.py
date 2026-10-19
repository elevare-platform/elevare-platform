"""Pydantic schemas for the credits module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreditBalanceResponse(BaseModel):
    """Response for GET /credits/balance.

    ``balance`` is everything the organization can spend. It is made up of
    ``plan_credits`` (included in its plan, spent first, replaced at each renewal
    and gone when the subscription ends) and ``purchased_credits`` (bought or
    granted, never expire). ``plan_credits_reset_at`` is when the plan credits are
    next replaced or end: the end of the current billing period.
    """

    balance: int
    plan_credits: int = 0
    purchased_credits: int = 0
    plan_credits_reset_at: datetime | None = None


class CreditHistoryItem(BaseModel):
    """One line of an organization's credit history.

    ``credits_change`` is positive when credits came in and negative when they
    were spent; ``plan_credits_change`` and ``purchased_credits_change`` say which
    pot it moved and add up to it. ``kind`` is a stable code a screen can pick an
    icon or colour from; ``description`` is the wording to show; ``detail`` is
    what it was for (the job), when there is one.
    """

    id: UUID
    created_at: datetime
    kind: str
    description: str
    detail: str | None = None
    credits_change: int
    plan_credits_change: int
    purchased_credits_change: int


class CreditHistoryPage(BaseModel):
    """A page of credit history, newest first. Pass ``next_cursor`` back as
    ``cursor`` for the next page; it is null on the last page."""

    items: list[CreditHistoryItem]
    next_cursor: str | None = None


class CreditGrantRequest(BaseModel):
    """Request body for PATCH /admin/employers/{employer_id}/credits."""

    amount: int = Field(..., gt=0, description="Number of credits to grant")
    reason: str | None = Field(None, max_length=200)
