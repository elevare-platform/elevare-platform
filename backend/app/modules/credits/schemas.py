"""Pydantic schemas for the credits module."""

from datetime import datetime

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


class CreditGrantRequest(BaseModel):
    """Request body for PATCH /admin/employers/{employer_id}/credits."""

    amount: int = Field(..., gt=0, description="Number of credits to grant")
    reason: str | None = Field(None, max_length=200)
