"""SQLAlchemy ORM models for the candidates module."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    ARRAY,
    UUID,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.ai.enums import CVParsingStatus
from app.modules.candidates.enums import VisibilityStatus
from app.modules.jobs.enums import WorkModel

if TYPE_CHECKING:
    from app.modules.jobs.models import Job
    from app.modules.users.models import User
    from app.modules.talent_pool.models import TalentPoolProfiles


class CandidateProfile(BaseModel):
    """Structured profile for candidate users.

    Stores skills, salary expectations, experience, and availability.
    ``is_profile_complete`` is flipped to True by the service layer once
    required fields are filled, unlocking job applications.
    """

    __tablename__ = "candidate_profile"

    # GIN Index definition
    __table_args__ = (
        Index(
            "ix_candidate_profile_skills_gin",  # Index name
            "skills",                   # Column name
            postgresql_using="gin"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_salary: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    expect3ed_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_work_models: Mapped[list[WorkModel] | None] = mapped_column(ARRAY(String), nullable=True)
    preferred_locations: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    is_profile_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    open_to_relocation: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    visibility: Mapped[VisibilityStatus] = mapped_column(
        String(15),
        nullable=False,
        default=VisibilityStatus.APPLIED_ONLY.value,
        server_default="APPLIED_ONLY",
    )

    cv_sharing_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="candidate_profile")
    cvs: Mapped[list[CandidateCvs]] = relationship(back_populates="candidate_profile")
    documents: Mapped[list[CandidateDocuments]] = relationship(back_populates="candidate_profile")
    work_experiences: Mapped[list[WorkExperience]] = relationship(back_populates="candidate_profile")
    educations: Mapped[list[Education]] = relationship(back_populates="candidate_profile")
    certifications: Mapped[list[Certification]] = relationship(back_populates="candidate_profile")
    profile_views: Mapped[list[ProfileView]] = relationship(back_populates="candidate_profile")
    talent_pool_profile: Mapped["TalentPoolProfiles | None"] = relationship(
        "TalentPoolProfiles",
        back_populates="candidate_profile",
        uselist=False,
    )


class CandidateCvs(BaseModel):
    """Uploaded CV files linked to a candidate profile.

    A candidate may have multiple CVs; ``is_default`` marks the one
    that is sent to employers by default.
    """

    __tablename__ = "candidate_cv"

    __table_args__ = (
        Index(
            "one_default_cv_per_candidate",
            "candidate_id",
            unique=True,
            postgresql_where=sa.text("is_default = true"),
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(
        Text
    )
    filename: Mapped[str] = mapped_column(
        String(255)
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        # DB enforces at most one is_default=True per candidate_id
        # via partial unique index: one_default_cv_per_candidate
    )
    cv_parse_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parsed_cv_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    cv_parse_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CVParsingStatus.PENDING.value,
        server_default=CVParsingStatus.PENDING.value,
    )

    # Relationships
    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="cvs")


class CandidateDocuments(BaseModel):
    """Supporting documents (certificates, portfolios, etc.) linked to a candidate profile."""

    __tablename__ = "candidate_documents"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(
        Text
    )
    filename: Mapped[str] = mapped_column(
        String(255)
    )
    document_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    candidate_profile: Mapped[CandidateProfile] = relationship(back_populates="documents")


class WorkExperience(BaseModel):
    """A single work experience entry on a candidate's profile."""

    __tablename__ = "candidate_work_experience"
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(String(255))
    job_title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa.false())

    # relationships
    candidate_profile: Mapped[CandidateProfile] = relationship(
        "CandidateProfile",
        back_populates="work_experiences",
    )


class Education(BaseModel):
    """An educational qualification entry on a candidate's profile."""

    __tablename__ = "candidate_education"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=False,
    )

    institution_name: Mapped[str] = mapped_column(String(255))
    degree: Mapped[str] = mapped_column(String(255))
    field_of_study: Mapped[str] = mapped_column(String(255))
    start_year: Mapped[int] = mapped_column(Integer, nullable=True)
    end_year: Mapped[int] = mapped_column(Integer, nullable=True)

    # relationships
    candidate_profile: Mapped[CandidateProfile] = relationship(
        "CandidateProfile",
        back_populates="educations",
    )


class Certification(BaseModel):
    """A professional certification or credential on a candidate's profile."""

    __tablename__ = "candidate_certification"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(255))
    issuing_organization: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiration_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    credential_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # relationships
    candidate_profile: Mapped[CandidateProfile] = relationship(
        "CandidateProfile",
        back_populates="certifications",
    )


class ProfileView(BaseModel):
    """Records when an employer views a candidate's profile."""

    __tablename__ = "profile_views"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate_profile.id", ondelete="CASCADE"),
        nullable=False,
    )
    employer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # relationships
    candidate_profile: Mapped[CandidateProfile] = relationship(
        "CandidateProfile",
        back_populates="profile_views",
        foreign_keys=[candidate_id],
    )
    employer: Mapped[User] = relationship(
        "User",
        foreign_keys=[employer_id],
        back_populates="profile_views_employer",
    )
    job: Mapped[Job] = relationship("Job")
