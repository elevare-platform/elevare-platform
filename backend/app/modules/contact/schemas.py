"""Pydantic schemas for the contact endpoint."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, EmailStr, field_validator


class InquiryType(str, Enum):
    general = "general"
    employer_inquiry = "employer_inquiry"


class ContactRequest(BaseModel):
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
        if len(v.strip()) < 20:
            raise ValueError("Message must be at least 20 characters.")
        return v


class ContactResponse(BaseModel):
    message: str
