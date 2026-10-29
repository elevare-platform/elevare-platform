"""Add the per-job switch for showing interview scores and bands

Revision ID: p22_0041
Revises: p22_0040

One new table (docs/08_DECISIONS.md, item 54): ``job_score_visibility``, one row for a job whose owner
or an Elevare admin has switched the interview score and the provisional band off (or on again).
A job with no row shows them, as every job did before. A table of its own, so ``jobs`` and
``job_interview_settings`` are untouched.

Safe on the live database: a new table, nothing existing is changed for the old code, and only the new
code reads it (guarded for the seconds before this runs).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0041"
down_revision: str | None = "p22_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_score_visibility",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("show_scores", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "changed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("job_score_visibility")
