"""Pydantic schemas for the credits module."""

from pydantic import BaseModel, Field


class CreditBalanceResponse(BaseModel):
    """Response for GET /credits/balance."""

    balance: int


class CreditGrantRequest(BaseModel):
    """Request body for PATCH /admin/employers/{employer_id}/credits."""

    amount: int = Field(..., gt=0, description="Number of credits to grant")
    reason: str | None = Field(None, max_length=200)
