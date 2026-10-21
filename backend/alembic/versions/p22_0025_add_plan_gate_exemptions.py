"""Add plan_gate_exemptions: organizations that keep Professional access

Revision ID: p22_0025
Revises: p22_0024

One row per organization an Elevare admin has exempted from plan gating (pilot
customers, partners, our own test accounts). ``organization_id`` is unique, so two
admins pressing "Add" at the same moment cannot create two rows. ``expires_at`` is
optional: NULL means the exemption never ends on its own.

Safe on the live database: a brand-new table that nothing else references, so no
existing row or query is affected, and the old code simply never looks at it.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0025"
down_revision: str | None = "p22_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_gate_exemptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", name="uq_plan_gate_exemptions_org"),
    )


def downgrade() -> None:
    op.drop_table("plan_gate_exemptions")
