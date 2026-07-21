"""Pydantic schemas for admin operations."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.modules.employer.schemas import KYCDocumentResponse
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


class KYCModerationRequest(BaseModel):
    """Payload for approving or rejecting an employer's KYC submission."""

    action: str  # "APPROVED" or "REJECTED"
    reason: str | None = None


class AdminKYCEmployerResponse(BaseModel):
    """Employer KYC submission for admin review."""

    employer_profile_id: UUID
    user_id: UUID
    company_name: str | None
    first_name: str
    last_name: str
    email: str
    kyc_status: str
    kyc_submitted_at: datetime | None
    kyc_reviewed_at: datetime | None
    kyc_rejection_reason: str | None
    documents: list[KYCDocumentResponse]

    @classmethod
    def from_profile(cls, profile) -> "AdminKYCEmployerResponse":
        """Build from an EmployerProfile ORM object with user/documents loaded."""
        return cls(
            employer_profile_id=profile.id,
            user_id=profile.user_id,
            company_name=profile.company_name,
            first_name=profile.user.first_name,
            last_name=profile.user.last_name,
            email=profile.user.email,
            kyc_status=profile.kyc_status,
            kyc_submitted_at=profile.kyc_submitted_at,
            kyc_reviewed_at=profile.kyc_reviewed_at,
            kyc_rejection_reason=profile.kyc_rejection_reason,
            documents=[KYCDocumentResponse.model_validate(d) for d in profile.kyc_documents],
        )


class CreditGrantRequest(BaseModel):
    """Payload for granting credits to an employer."""

    amount: int = Field(..., gt=0)
    reason: str | None = Field(None, max_length=200)


class AuditLogAdminSummary(BaseModel):
    """Safe admin summary embedded in audit log entries — no sensitive fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: str


class AuditLogResponse(BaseModel):
    """Safe audit log entry — excludes raw admin ORM object."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    action: str
    reason: str | None = None
    target_type: str
    target_id: UUID
    log_metadata: dict | None = None
    admin: AuditLogAdminSummary | None = None
