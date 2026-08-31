"""Add credit_packages table — purchasable credit bundles

Revision ID: p22_0003
Revises: p22_0002
"""
import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0003"
down_revision: str | None = "p22_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credit_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("price_kobo", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("price_kobo >= 0", name="ck_credit_packages_price_non_negative"),
        sa.UniqueConstraint("code", name="uq_credit_packages_code"),
    )

    packages_table = sa.table(
        "credit_packages",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("credits", sa.Integer),
        sa.column("price_kobo", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        packages_table,
        [
            {
                "id": uuid.uuid4(),
                "code": "starter_pack",
                "name": "Starter Pack",
                "credits": 10,
                "price_kobo": 1_500_000,  # ₦15,000
                "currency": "NGN",
                "is_active": True,
                "sort_order": 0,
            },
            {
                "id": uuid.uuid4(),
                "code": "growth_pack",
                "name": "Growth Pack",
                "credits": 50,
                "price_kobo": 6_500_000,  # ₦65,000
                "currency": "NGN",
                "is_active": True,
                "sort_order": 1,
            },
            {
                "id": uuid.uuid4(),
                "code": "scale_pack",
                "name": "Scale Pack",
                "credits": 150,
                "price_kobo": 18_000_000,  # ₦180,000
                "currency": "NGN",
                "is_active": True,
                "sort_order": 2,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("credit_packages")
