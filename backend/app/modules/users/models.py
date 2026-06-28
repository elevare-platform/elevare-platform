"""SQLAlchemy ORM models for the users module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

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
    from app.modules.candidates.models import CandidateProfile, ProfileView
    from app.modules.jobs.models import Job, JobAccessTokens
    from app.modules.talent_pool.models import TalentPoolProfiles


class User(BaseModel):
    """Core user account — stores credentials, role, and account lifecycle state."""

    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    last_name: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True
    )
    phone_number: Mapped[str] = mapped_column(
        String(15),
        unique=True,
        nullable=True,
        index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AccountStatus.PENDING_VERIFICATION.value,
        server_default=AccountStatus.PENDING_VERIFICATION.value
    )
    role: Mapped[UserRole] = mapped_column(
        String(20),
        nullable=False,
        default=UserRole.CANDIDATE.value,
        server_default=UserRole.CANDIDATE.value
    )
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    email_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )


    # Relationships
    profile: Mapped[UserProfile] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False
    )
    employer_profile: Mapped[EmployerProfile] = relationship(
        "EmployerProfile",
        back_populates="user",
        uselist=False,
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
        "EmailVerificationToken",
        back_populates="user"
    )
    invite_tokens: Mapped[list[InviteToken]] = relationship(
        "InviteToken",
        back_populates="inviter"
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
        "AuditLog",
        back_populates="admin"
    )
    cv_uploader: Mapped[list[ParsedCVSubmission]] = relationship(
        "ParsedCVSubmission",
        back_populates="uploader"
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





class UserProfile(BaseModel):
    """Optional user profile — avatar and location details for any user type."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    avatar_url: Mapped[str] = mapped_column(
        String(255),
        nullable=True,
    )
    city: Mapped[str] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(255), nullable=True)

    # relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="profile"
    )


class EmployerProfile(BaseModel):
    """Company profile for employer accounts.

    Created when an employer registers. Fields are nullable until the
    employer completes their profile. ``is_profile_complete`` is flipped
    to True by the service layer when required fields are filled.
    """

    __tablename__ = "employer_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=True)
    company_description: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )
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

    # relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="employer_profile",
    )

