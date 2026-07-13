"""SQLAlchemy ORM model for the admin audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import UUID, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.users.models import User


class AuditLog(Base):
    """Records every significant admin action for audit and compliance purposes."""

    __tablename__ = "admin_audit_log"
    __table_args__ = (Index("idx_target_type_id", "target_type", "target_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=True)

    target_type: Mapped[str] = mapped_column(String(255), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    log_metadata: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # relationships
    admin: Mapped[User] = relationship(back_populates="audit_logs")
