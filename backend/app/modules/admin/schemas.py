"""Pydantic schemas for admin operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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


# ---------------------------------------------------------------------------
# Admin response schemas — safe serialization (no Vector/embedding fields)
# ---------------------------------------------------------------------------


class AdminEmployerProfileResponse(BaseModel):
    """Employer profile fields for admin user detail responses."""

    model_config = ConfigDict(from_attributes=True)

    company_name: str | None = None
    company_description: str | None = None
    industry: str | None = None
    company_size: str | None = None
    website: str | None = None
    company_logo_url: str | None = None
    is_profile_complete: bool = False


class AdminUserResponse(BaseModel):
    """Safe user representation for admin endpoints — excludes sensitive and unserializable fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str
    phone_number: str | None = None
    role: str
    account_status: str
    email_verified: bool
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    created_at: datetime
    employer_profile: AdminEmployerProfileResponse | None = None


class AdminApplicationResponse(BaseModel):
    """Safe application representation for admin endpoints."""

    id: UUID
    candidate_id: UUID
    job_id: UUID
    status: str
    cover_letter: str | None = None
    match_score: int | None = None
    ai_score: int | None = None
    ai_fit_summary: str | None = None
    ai_strengths: list[str] | None = None
    ai_weaknesses: list[str] | None = None
    ai_score_computed_at: datetime | None = None
    status_updated_at: datetime
    created_at: datetime
    # Flattened from relationships
    job_title: str | None = None
    candidate_name: str | None = None
    candidate_email: str | None = None

    @classmethod
    def from_application(cls, app) -> "AdminApplicationResponse":
        """Build from a raw Application ORM object."""
        job = getattr(app, "job", None)
        candidate = getattr(app, "candidate", None)
        return cls(
            id=app.id,
            candidate_id=app.candidate_id,
            job_id=app.job_id,
            status=app.status,
            cover_letter=app.cover_letter,
            match_score=app.match_score,
            ai_score=app.ai_score,
            ai_fit_summary=app.ai_fit_summary,
            ai_strengths=app.ai_strengths,
            ai_weaknesses=app.ai_weaknesses,
            ai_score_computed_at=app.ai_score_computed_at,
            status_updated_at=app.status_updated_at,
            created_at=app.created_at,
            job_title=job.title if job else None,
            candidate_name=(
                f"{candidate.first_name} {candidate.last_name}".strip()
                if candidate
                else None
            ),
            candidate_email=candidate.email if candidate else None,
        )


class CreditGrantRequest(BaseModel):
    """Payload for granting credits to an employer."""

    amount: int = Field(..., gt=0)
    reason: str | None = Field(None, max_length=200)
