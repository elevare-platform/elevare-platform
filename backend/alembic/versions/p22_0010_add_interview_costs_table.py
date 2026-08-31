"""Add interview_costs table

Revision ID: p22_0010
Revises: p22_0009

Cost tracking for the AI video interview feature — one row per billed
external call tied to an interview (realtime session, Whisper
transcription fallback, Claude scoring). See app/core/ai_pricing.py.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0010"
down_revision: str | None = "p22_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_costs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("interview_id", sa.UUID(), nullable=False),
        sa.Column("component", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(10, 2), nullable=True),
        sa.Column("usage_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
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
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interview_costs_interview_id", "interview_costs", ["interview_id"]
    )
    op.create_index(
        "ix_interview_costs_created_at", "interview_costs", ["created_at"]
    )
    op.create_index(
        "ix_interview_costs_component", "interview_costs", ["component"]
    )


def downgrade() -> None:
    op.drop_index("ix_interview_costs_component", table_name="interview_costs")
    op.drop_index("ix_interview_costs_created_at", table_name="interview_costs")
    op.drop_index("ix_interview_costs_interview_id", table_name="interview_costs")
    op.drop_table("interview_costs")
