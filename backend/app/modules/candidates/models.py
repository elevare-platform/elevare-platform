"""SQLAlchemy ORM models for the candidates module."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    ARRAY,
    UUID,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel

if TYPE_CHECKING:
    from app.modules.users.models import User


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
        nullable=False,
        unique=True,
    )

    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expected_salary: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    expected_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notice_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_profile_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )

    # Relationships
    user: Mapped[User] = relationship(back_populates="candidate_profile")
    cvs: Mapped[list[CandidateCvs]] = relationship(back_populates="candidate_profile")
    documents: Mapped[list[CandidateDocuments]] = relationship(back_populates="candidate_profile")


class CandidateCvs(BaseModel):
    """Uploaded CV files linked to a candidate profile.

    A candidate may have multiple CVs; ``is_default`` marks the one
    that is sent to employers by default.
    """

    __tablename__ = "candidate_cv"

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

