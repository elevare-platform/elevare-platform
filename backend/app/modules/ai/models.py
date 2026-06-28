from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    ARRAY,
    UUID,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.ai.enums import CVParsingStatus

if TYPE_CHECKING:
    from app.modules.users.models import User
    from app.modules.talent_pool.models import TalentPoolProfiles


class ParsedCVSubmission(BaseModel):
    __tablename__ = "parsed_cv_submissions"

    __table_args__ = (
        Index("ix_parsed_cv_submissions_uploaded_by", "uploaded_by"),
        Index("ix_parsed_cv_submissions_parse_status", "parse_status"),
        Index("ix_parsed_cv_submissions_cv_text_hash", "cv_text_hash"),
    )

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    r2_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    cv_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CVParsingStatus.PENDING.value,
        server_default=CVParsingStatus.PENDING.value,
    )
    parsed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    deterministic_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    flag_reasons: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    uploader: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[uploaded_by],
    )
    parsing_costs: Mapped[list[CVParsingCost]] = relationship(
        "CVParsingCost",
        back_populates="submission",
    )
    talent_pool_profile: Mapped["TalentPoolProfiles"] = relationship(
        "TalentPoolProfiles",
        back_populates="parsed_submission",
        uselist=False,
    )


class CVParsingCost(BaseModel):
    __tablename__ = "cv_parsing_costs"

    __table_args__ = (
        Index("ix_cv_parsing_costs_submission_id", "submission_id"),
        Index("ix_cv_parsing_costs_created_at", "created_at"),
    )

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("parsed_cv_submissions.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(sa.Numeric(10, 6), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    submission: Mapped[ParsedCVSubmission] = relationship(
        "ParsedCVSubmission",
        back_populates="parsing_costs",
    )
