"""add mail_integrations and ingestion_import_runs tables

Revision ID: p16a_0001
Revises: cd5ec87a801b
Create Date: 2026-07-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p16a_0001"
down_revision: Union[str, None] = "cd5ec87a801b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mail_integrations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False, server_default="GMAIL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="CONNECTED"),
        sa.Column("encrypted_access_token", sa.Text, nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_address", sa.String(255), nullable=True),
        sa.Column("sync_cursor", sa.String(100), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "user_id", "provider", name="uq_mail_integration_user_provider"
        ),
    )
    op.create_index("ix_mail_integrations_user_id", "mail_integrations", ["user_id"])
    op.create_index("ix_mail_integrations_status", "mail_integrations", ["status"])

    op.create_table(
        "ingestion_import_runs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "integration_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("mail_integrations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("total_emails_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("emails_processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("emails_skipped", sa.Integer, nullable=False, server_default="0"),
        sa.Column("emails_failed", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "emails_deduplicated", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("query_filter", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ingestion_import_runs_integration_id",
        "ingestion_import_runs",
        ["integration_id"],
    )
    op.create_index(
        "ix_ingestion_import_runs_status", "ingestion_import_runs", ["status"]
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_import_runs_status", "ingestion_import_runs")
    op.drop_index("ix_ingestion_import_runs_integration_id", "ingestion_import_runs")
    op.drop_table("ingestion_import_runs")

    op.drop_index("ix_mail_integrations_status", "mail_integrations")
    op.drop_index("ix_mail_integrations_user_id", "mail_integrations")
    op.drop_table("mail_integrations")
