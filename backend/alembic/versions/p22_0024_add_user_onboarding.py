"""Add user_onboarding: where each user is in the first-login tour and checklist

Revision ID: p22_0024
Revises: p22_0023

One row per user, created the first time the tour or checklist records something. No
row means the user has not seen the tour yet. ``completed_steps`` holds the checklist
steps the user has done that the server cannot work out for itself (opening the talent
pool, trying candidate search and so on).

Safe on the live database: a brand-new table that nothing else references, so no
existing row or query is affected. Deleting a user deletes their row.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0024"
down_revision: str | None = "p22_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_onboarding",
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
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tour_outcome", sa.String(20), nullable=True),
        sa.Column("tour_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checklist_dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "completed_steps",
            postgresql.ARRAY(sa.String(40)),
            server_default="{}",
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", name="uq_user_onboarding_user_id"),
    )


def downgrade() -> None:
    op.drop_table("user_onboarding")
