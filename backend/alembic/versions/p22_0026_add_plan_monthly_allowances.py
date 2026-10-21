"""Add the monthly CV-upload and AI-scoring allowances to plans

Revision ID: p22_0026
Revises: p22_0025

``monthly_cv_uploads`` and ``monthly_ai_scores`` say how many CV reads and AI scores a
company on the plan gets per calendar month (Lagos time). NULL means unlimited, 0 means
none. The values are the user's decisions of 2026-10-21 (docs/08_DECISIONS.md):

    Starter       10 uploads, 0 AI scores (the free taste of scoring is handled in code)
    Professional  100 uploads, 500 AI scores
    Enterprise    unlimited until it is set for a customer

Safe on the live database: two nullable columns on a tiny table, and one UPDATE per seeded
plan. Nothing reads the columns until the allowance check is switched on, and the old code
ignores them. The Enterprise plan keeps NULL (unlimited).
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0026"
down_revision: str | None = "p22_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("monthly_cv_uploads", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("monthly_ai_scores", sa.Integer(), nullable=True))
    op.execute(
        "UPDATE plans SET monthly_cv_uploads = 10, monthly_ai_scores = 0 WHERE code = 'starter'"
    )
    op.execute(
        "UPDATE plans SET monthly_cv_uploads = 100, monthly_ai_scores = 500 "
        "WHERE code = 'professional'"
    )


def downgrade() -> None:
    op.drop_column("plans", "monthly_ai_scores")
    op.drop_column("plans", "monthly_cv_uploads")
