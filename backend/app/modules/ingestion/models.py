"""SQLAlchemy ORM models for the candidate ingestion module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List

import sqlalchemy as sa
from sqlalchemy import UUID, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import BaseModel
from app.modules.ingestion.enums import ImportStatus, IntegrationStatus, MailProvider

if TYPE_CHECKING:
    from app.modules.users.models import User


class MailIntegration(BaseModel):
    """A connected mailbox belonging to a user (internal admin, or later, an employer).

    Stores encrypted OAUth tokens, never a plain text.
    ``sync_cursor` is provider specific:
    - Gmail: the ``historyId`` string from the last history.list call
    - Zoho: the ``modifiedTime`` cursor (Later Implementation)
    """

    __tablename__ = "mail_integrations"

    __table_args__ = (
        # One integration per user per provider per email address
        # (Zoho users may have multiple accounts under one login)
        sa.UniqueConstraint(
            "user_id",
            "provider",
            "email_address",
            name="uq_mail_integration_user_provider_email",
        ),
        Index("ix_mail_integrations_user_id", "user_id"),
        Index("ix_mail_integrations_status", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MailProvider.GMAIL.value,
        server_default=MailProvider.GMAIL.value,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=IntegrationStatus.CONNECTED.value,
        server_default=IntegrationStatus.CONNECTED.value,
    )

    # Encrypted access token / Encrypted refresh token (bytes stored as hex string) - decrypted only in service layer
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Token expiry is used to decide when to refresh without decrypting unnecessarily
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    email_address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Provider specific cursor for incremental sync (Gmail: historyId, Zoho: modifiedTime, etc.)
    sync_cursor: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time the user's mailbox was synced with the system",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if the sync failed",
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="mail_integrations",
        lazy="selectin",
    )

    import_runs: Mapped[List["IngestionImportRun"]] = relationship(
        "IngestionImportRun",
        back_populates="integration",
        order_by="IngestionImportRun.created_at.desc()",
    )


class IngestionImportRun(BaseModel):
    """Tracks a single historical import attempt for a mail integration.

    Gives us a full observability: how many emails were found, processed,
    skipped (no CV attachments), and failed.
    ``started_at`` / ``completed`` let us measure import duration.
    """

    __tablename__ = "ingestion_import_runs"

    __table_args__ = (
        sa.Index("ix_ingestion_import_runs_integration_id", "integration_id"),
        sa.Index("ix_ingestion_import_runs_status", "status"),
    )

    integration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mail_integrations.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ImportStatus.PENDING.value,
        server_default=ImportStatus.PENDING.value,
    )

    total_emails_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Successfully queued into the CV parsing pipeline
    emails_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Skipped — no CV attachment, wrong file type, or size violation
    emails_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Failed with an error during processing
    emails_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Deduplicated — CV hash matched an existing submission, no re-parse needed
    emails_deduplicated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optional: search query used to scope the import (e.g. "subject:CV OR subject:resume")
    query_filter: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    integration: Mapped[MailIntegration] = relationship(
        "MailIntegration",
        back_populates="import_runs",
    )
