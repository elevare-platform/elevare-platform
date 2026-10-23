"""Add job.published_at, job.disabled_reason, job.disabled_at and organizations.taste_job_id

Revision ID: p22_0027
Revises: p22_0026

Stage 2 of the plan limits (docs/08_DECISIONS.md, "Plan limits, consolidated"):

* ``jobs.published_at``: when a job last went live. The Starter plan's "one job a month"
  and "30 days" both run from it. Jobs that are already live or closed get their
  ``created_at`` as the value (the best date the platform has); drafts stay NULL.
* ``jobs.disabled_reason`` and ``jobs.disabled_at``: set while a job is DISABLED (the new
  job status, a plain string, so no database type changes).
* ``organizations.taste_job_id``: the company's free taste, its first published job. NULL
  for every existing company, so each existing company's NEXT published job becomes its
  taste (the generous way round for companies that already use the platform).

Safe on the live database: four nullable columns and one UPDATE on the jobs table. The old
code ignores the new columns, and nothing acts on them until the Starter rules are built
and plan gating is switched on.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0027"
down_revision: str | None = "p22_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("disabled_reason", sa.String(30), nullable=True))
    op.add_column("jobs", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE jobs SET published_at = created_at WHERE status IN ('ACTIVE', 'CLOSED')")

    op.add_column(
        "organizations",
        sa.Column("taste_job_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_organizations_taste_job_id",
        "organizations",
        "jobs",
        ["taste_job_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_organizations_taste_job_id", "organizations", type_="foreignkey")
    op.drop_column("organizations", "taste_job_id")
    op.drop_column("jobs", "disabled_at")
    op.drop_column("jobs", "disabled_reason")
    op.drop_column("jobs", "published_at")
