"""Phase 18 — Add generic notifications table.

Revision ID: p18_0001
Revises: p16b_0001
Create Date: 2026-07-22 00:00:00.000000

Design notes:
    - Generic schema: recipient_id + type + title + body + entity_type + entity_id + read_at
    - Not match-specific — serves future email triggers, status changes, etc.
    - WebSocket push deferred to a later phase; v1 delivers on next load.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "p18_0001"
down_revision: Union[str, None] = "p16b_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(60), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(60), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_recipient_id", "notifications", ["recipient_id"], unique=False
    )
    op.create_index(
        "ix_notifications_read_at", "notifications", ["read_at"], unique=False
    )
    op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_read_at", table_name="notifications")
    op.drop_index("ix_notifications_recipient_id", table_name="notifications")
    op.drop_table("notifications")
