"""Make cv_parsing_costs.cost_usd nullable

Revision ID: p22_0011
Revises: p22_0010

A model missing from app/core/ai_pricing.py's rate table now still gets a
cost row with real token counts and cost_usd=NULL, rather than a wrong
$0.00 or a silently dropped row — NULL is visibly different from a
computed number in the admin cost summary.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0011"
down_revision: str | None = "p22_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "cv_parsing_costs", "cost_usd", existing_type=sa.Numeric(10, 6), nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        "cv_parsing_costs", "cost_usd", existing_type=sa.Numeric(10, 6), nullable=False
    )
