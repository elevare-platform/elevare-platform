"""Pydantic schemas for admin operations."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.enums import AccountStatus, UserRole


class InviteRequest(BaseModel):
    """Payload for creating an employer invite.

    Attributes
    ----------
        email: The email address to send the invite to.
        role: The role to assign to the invited user.

    """

    email: EmailStr
    role: UserRole


class UserStatusUpdateRequest(BaseModel):
    """Payload for updating a user's account status."""

    status: AccountStatus


class BulkUserActionRequest(BaseModel):
    """Payload for bulk user status updates."""

    user_ids: list[UUID] = Field(..., max_length=100)
    action: str  # "activate" or "deactivate"


class JobModerationRequest(BaseModel):
    """Payload for moderating a job."""

    action: str  # "APPROVED", "REJECTED", "close"
    reason: str | None = None


class BulkJobActionRequest(BaseModel):
    """Payload for bulk job actions."""

    job_ids: list[UUID] = Field(..., max_length=100)
    action: str
