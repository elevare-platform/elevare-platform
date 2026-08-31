"""SQLAlchemy ORM models for the users module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.employer.enums import KYCStatus

from .enums import AccountStatus, UserRole

if TYPE_CHECKING:
    from app.modules.admin.models import AuditLog
    from app.modules.ai.models import ParsedCVSubmission
    from app.modules.applications.models import Application
    from app.modules.auth.models import (
        EmailVerificationToken,
        InviteToken,
        RefreshToken,
    )
    from app.modules.billing.models import Payment, Subscription
    from app.modules.candidates.models import CandidateProfile, ProfileView
    from app.modules.credits.models import CreditTransaction, EmployerCredits
    from app.modules.employer.models import KYCDocument
    from app.modules.ingestion.models import MailIntegration
    from app.modules.introductions.models import IntroductionRequest
    from app.modules.jobs.models import Job, JobAccessTokens
    from app.modules.notifications.models import Notification
    from app.modules.talent_pool.models import TalentPoolProfiles


class User(BaseModel):
    """Core user account — stores credentials, role, and account lifecycle state."""

    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(30), nullable=False)
    last_name: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    phone_number: Mapped[str] = mapped_column(
        String(15), unique=True, nullable=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    account_status: Mapped[AccountStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AccountStatus.PENDING_VERIFICATION.value,
        server_default=AccountStatus.PENDING_VERIFICATION.value,
    )
    role: Mapped[UserRole] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.CANDIDATE.value,
        server_default=UserRole.CANDIDATE.value,
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    email_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Organization membership ---
    # A User belongs to at most one Organization (enforced nowhere at the DB
    # level today since it's a plain nullable FK, not a unique one-to-many
    # child key — revisit if that ever needs enforcing). organization_role
    # is a separate axis from `role` above: `role` is platform-wide
    # (EMPLOYER/CANDIDATE/ADMIN), organization_role is who can manage this
    # specific company's billing/team (OWNER/ADMIN/MEMBER).
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_role: Mapped[str] = mapped_column(String(20), nullable=True)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    joined_organization_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    profile: Mapped[UserProfile] = relationship(
        "UserProfile", back_populates="user", uselist=False
    )
    organization: Mapped[Organization] = relationship(
        "Organization",
        back_populates="members",
        foreign_keys=[organization_id],
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
    )
    jobs: Mapped[list[Job]] = relationship(
        "Job",
        back_populates="employer",
    )
    email_verification_tokens: Mapped[list[EmailVerificationToken]] = relationship(
        "EmailVerificationToken", back_populates="user"
    )
    invite_tokens: Mapped[list[InviteToken]] = relationship(
        "InviteToken", back_populates="inviter"
    )
    candidate_profile: Mapped[CandidateProfile] = relationship(
        "CandidateProfile",
        back_populates="user",
        uselist=False,
    )
    application_updated_by: Mapped[Application] = relationship(
        "Application",
        back_populates="who_updated_status",
        foreign_keys="Application.status_updated_by",
    )
    applications: Mapped[list[Application]] = relationship(
        "Application",
        back_populates="candidate",
        foreign_keys="Application.candidate_id",
    )
    profile_views_employer: Mapped[list[ProfileView]] = relationship(
        "ProfileView",
        back_populates="employer",
        foreign_keys="ProfileView.employer_id",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="admin"
    )
    cv_uploader: Mapped[list[ParsedCVSubmission]] = relationship(
        "ParsedCVSubmission", back_populates="uploader"
    )
    job_access_tokens_created_by: Mapped[list[JobAccessTokens]] = relationship(
        "JobAccessTokens",
        back_populates="created_by",
        foreign_keys="JobAccessTokens.created_by_id",
    )
    job_access_tokens_revoked_by: Mapped[list[JobAccessTokens]] = relationship(
        "JobAccessTokens",
        back_populates="revoked_by",
        foreign_keys="JobAccessTokens.revoked_by_id",
    )
    talent_pool_added_by: Mapped[list[TalentPoolProfiles]] = relationship(
        "TalentPoolProfiles",
        back_populates="added_by_user",
        foreign_keys="TalentPoolProfiles.added_by",
    )
    mail_integrations: Mapped[list[MailIntegration]] = relationship(
        "MailIntegration",
        back_populates="user",
    )
    introduction_requests: Mapped[list[IntroductionRequest]] = relationship(
        "IntroductionRequest",
        back_populates="employer",
    )
    notifications: Mapped[list[Notification]] = relationship(
        "Notification",
        back_populates="recipient",
        foreign_keys="Notification.recipient_id",
    )


class UserProfile(BaseModel):
    """Optional user profile — avatar and location details for any user type."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    avatar_url: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(255), nullable=True)

    # relationships
    user: Mapped[User] = relationship("User", back_populates="profile")


class Organization(BaseModel):
    """A company/employer account. Owns billing, KYC, and one or more `User` members.

    Created when the first employer for a company registers (that user
    becomes ``OWNER``, see ``User.organization_role``); teammates join the
    same row via invite rather than getting their own. Company fields are
    nullable until the profile is completed; ``is_profile_complete`` is
    flipped to True by the service layer when required fields are filled.

    Named ``Organization`` rather than ``EmployerProfile`` — the earlier
    name implied a 1:1 relationship with a single login, which stopped
    being true once billing/KYC needed to be shared across a company's
    staff.
    """

    __tablename__ = "organizations"

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=True)
    company_description: Mapped[str] = mapped_column(Text, nullable=True)
    company_logo_url: Mapped[str] = mapped_column(String(500), nullable=True)
    industry: Mapped[str] = mapped_column(String(100), nullable=True)
    company_size: Mapped[str] = mapped_column(String(20), nullable=True)
    website: Mapped[str] = mapped_column(String(500), nullable=True)
    is_profile_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )

    # =================== KYC ===========================
    kyc_status: Mapped[KYCStatus] = mapped_column(
        String(20),
        nullable=True,
        default=KYCStatus.NOT_SUBMITTED.value,
        server_default=KYCStatus.NOT_SUBMITTED.value,
    )
    kyc_rejection_reason: Mapped[str] = mapped_column(Text, nullable=True)
    kyc_submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    kyc_reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    members: Mapped[list[User]] = relationship(
        "User",
        back_populates="organization",
        foreign_keys="User.organization_id",
    )
    kyc_documents: Mapped[list[KYCDocument]] = relationship(
        "KYCDocument",
        back_populates="organization",
    )
    credit_transactions: Mapped[list[CreditTransaction]] = relationship(
        "CreditTransaction",
        back_populates="organization",
    )
    employer_credits: Mapped[EmployerCredits | None] = relationship(
        "EmployerCredits",
        back_populates="organization",
        uselist=False,
    )
    subscription: Mapped[Subscription | None] = relationship(
        "Subscription",
        back_populates="organization",
        uselist=False,
    )
    payments: Mapped[list[Payment]] = relationship(
        "Payment",
        back_populates="organization",
    )
