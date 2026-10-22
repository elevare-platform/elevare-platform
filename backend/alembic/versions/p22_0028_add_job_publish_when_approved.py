"""Add jobs.publish_when_approved

Revision ID: p22_0028
Revises: p22_0027

An employer can tick "publish as soon as it is approved" when posting a job, so they do not have
to come back and press Publish after an admin approves it (docs/08_DECISIONS.md, the job review
flow). False for every existing job, which keeps today's behaviour.

Safe on the live database: one NOT NULL column with a constant default on the jobs table (an
instant change in current PostgreSQL), nothing reads it until the approval step is changed, and
the old code ignores it.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0028"
down_revision: str | None = "p22_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "publish_when_approved",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "publish_when_approved")
