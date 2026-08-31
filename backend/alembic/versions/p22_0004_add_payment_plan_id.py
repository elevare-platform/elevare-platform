"""Add plan_id to payments — lets subscription checkout finalize know which plan to activate

Revision ID: p22_0004
Revises: p22_0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0004"
down_revision: str | None = "p22_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "payments_plan_id_fkey",
        "payments",
        "plans",
        ["plan_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("payments_plan_id_fkey", "payments", type_="foreignkey")
    op.drop_column("payments", "plan_id")
