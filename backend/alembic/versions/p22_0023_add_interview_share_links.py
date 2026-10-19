"""Add interview_share_links: a read-only link to a job's interview results

Revision ID: p22_0023
Revises: p22_0022

One row per link an employer (or Elevare staff running interviews for a client) creates
to show a job's interview results, with no login. The link expires and can be revoked.
There is at most ONE active (not revoked) link per job, enforced by a partial unique
index, so two people pressing "Share" at the same moment cannot create two live links.

``view_count`` and ``last_viewed_at`` say whether the link has been opened.

Safe on the live database: a brand-new table that nothing else references, so no existing
row or query is affected.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0023"
down_revision: str | None = "p22_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_share_links",
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
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("view_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("token", name="uq_interview_share_links_token"),
    )
    op.create_index("ix_interview_share_links_job_id", "interview_share_links", ["job_id"])
    op.create_index(
        "uq_interview_share_one_active_per_job",
        "interview_share_links",
        ["job_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_interview_share_one_active_per_job", table_name="interview_share_links")
    op.drop_index("ix_interview_share_links_job_id", table_name="interview_share_links")
    op.drop_table("interview_share_links")
