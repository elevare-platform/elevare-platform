"""Pydantic schemas for admin operations."""

from pydantic import BaseModel, EmailStr

from app.modules.users.enums import UserRole


class InviteRequest(BaseModel):
    """Payload for creating an employer invite.

    Attributes:
        email: The email address to send the invite to.
        role: The role to assign to the invited user.

    """

    email: EmailStr
    role: UserRole
