from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.modules.testimonials.enums import TestimonialStatus


class TestimonialCreate(BaseModel):
    full_name: str
    company: str | None = None
    position: str | None = None
    testimony: str
    image: str | None = None  # R2 key, set internally by the service

    @field_validator("full_name", "testimony")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field cannot be empty.")
        return v.strip()


class TestimonialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    company: str | None
    position: str | None
    testimony: str
    image_url: str | None  # resolved public URL, not raw R2 key
    created_at: datetime


class TestimonialAdminRead(BaseModel):
    """Full representation for admin — includes status and reviewed_at."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    company: str | None
    position: str | None
    testimony: str
    image_url: str | None  # resolved public URL, not raw R2 key
    status: TestimonialStatus
    reviewed_at: datetime | None
    created_at: datetime


class TestimonialModerationRequest(BaseModel):
    status: TestimonialStatus

    @field_validator("status")
    @classmethod
    def not_pending(cls, v: TestimonialStatus) -> TestimonialStatus:
        # Admins can set approved, rejected, or reset back to pending
        return v


class TestimonialResponse(BaseModel):
    message: str
