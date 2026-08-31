"""Add checkout_url + expiry to payments — dedup cache for start_checkout

Revision ID: p22_0002
Revises: p22_0001
"""
import sqlalchemy as sa
from alembic import op

revision: str = "p22_0002"
down_revision: str | None = "p22_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("checkout_url", sa.Text(), nullable=True))
    op.add_column(
        "payments",
        sa.Column("checkout_url_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("payments", "checkout_url_expires_at")
    op.drop_column("payments", "checkout_url")
