"""Pydantic schemas for the contact endpoint."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, EmailStr, field_validator


class InquiryType(str, Enum):
    """Type of contact form inquiry."""

    general = "general"
    employer_inquiry = "employer_inquiry"


class ContactRequest(BaseModel):
    """Payload for a contact form submission."""

    name: str
    email: EmailStr
    company: str | None = None
    message: str
    inquiry_type: InquiryType = InquiryType.general
    # Honeypot — must be empty on legitimate submissions
    honeypot: str | None = None

    @field_validator("message")
    @classmethod
    def message_min_length(cls, v: str) -> str:
        """Enforce a minimum message length of 20 characters."""
        if len(v.strip()) < 20:
            raise ValueError("Message must be at least 20 characters.")
        return v


class ContactResponse(BaseModel):
    """Response returned after a contact form submission."""

    message: str
