"""Add fit_scoring_costs table

Revision ID: p22_0012
Revises: p22_0011

Cost tracking for the LLM candidate-vs-job "fit reasoning" call
(generate_fit_reasoning), triggered from either the Application scoring
flow or the talent-pool "score against job" flow — previously untracked.
See app/core/ai_pricing.py.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0012"
down_revision: str | None = "p22_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fit_scoring_costs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("talent_pool_profile_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["talent_pool_profile_id"], ["talent_pool_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fit_scoring_costs_application_id", "fit_scoring_costs", ["application_id"]
    )
    op.create_index(
        "ix_fit_scoring_costs_talent_pool_profile_id",
        "fit_scoring_costs",
        ["talent_pool_profile_id"],
    )
    op.create_index(
        "ix_fit_scoring_costs_created_at", "fit_scoring_costs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fit_scoring_costs_created_at", table_name="fit_scoring_costs"
    )
    op.drop_index(
        "ix_fit_scoring_costs_talent_pool_profile_id", table_name="fit_scoring_costs"
    )
    op.drop_index(
        "ix_fit_scoring_costs_application_id", table_name="fit_scoring_costs"
    )
    op.drop_table("fit_scoring_costs")
