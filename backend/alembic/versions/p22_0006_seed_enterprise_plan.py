"""Seed an inactive Enterprise plan row

Revision ID: p22_0006
Revises: p22_0005

Enterprise is sales-negotiated, not self-serve (matches PricingPage.jsx's
"Contact Sales" CTA) — is_active=False keeps it out of GET /billing/plans
and out of self-serve checkout. It still needs a real row so an admin-comp
flow (Phase 4) has something for Subscription.plan_id to point at, and so
"is this org on Professional or above" checks naturally include Enterprise
without special-casing it.
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0006"
down_revision: str | None = "p22_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    plans_table = sa.table(
        "plans",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("price_kobo", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("interval", sa.String),
        sa.column("job_posting_limit", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        plans_table,
        [
            {
                "id": uuid.uuid4(),
                "code": "enterprise",
                "name": "Enterprise",
                "description": "Custom, sales-negotiated — contact sales.",
                "price_kobo": 0,  # placeholder — no self-serve price, comped by admin
                "currency": "NGN",
                "interval": "MONTHLY",
                "job_posting_limit": None,
                "is_active": False,
                "sort_order": 2,
            },
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE code = 'enterprise'")
