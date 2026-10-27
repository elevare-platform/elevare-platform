"""Add the per-job follow-up mode and the probes on a question

Revision ID: p22_0034
Revises: p22_0033

One new table and two nullable columns, all on tables that only this branch introduced
(docs/08_DECISIONS.md, item 40):

* ``job_interview_settings``: how a job's strict interview behaves beyond its questions, for now
  the follow-up mode (NONE, STANDARD or PROBES_ONLY). A table of its own, NOT a column on
  ``jobs``: a new column on ``jobs`` would break every job query between the new containers
  starting and this migration finishing.
* ``job_interview_questions.probes``: the employer's own follow-up probes for a question, one per
  line. Nullable; the table is new in p22_0029, so no live row is rewritten.
* ``interview_strict_runs.follow_up_mode``: the mode copied when an interview starts. Nullable;
  a run without one is the standard. The table is new in p22_0030.

Safe on the live database: nothing existing is changed for the old code.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0034"
down_revision: str | None = "p22_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_interview_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("follow_up_mode", sa.String(12), nullable=False, server_default="STANDARD"),
        sa.UniqueConstraint("job_id", name="uq_job_interview_settings_job"),
    )
    op.add_column("job_interview_questions", sa.Column("probes", sa.Text(), nullable=True))
    op.add_column("interview_strict_runs", sa.Column("follow_up_mode", sa.String(12), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_strict_runs", "follow_up_mode")
    op.drop_column("job_interview_questions", "probes")
    op.drop_table("job_interview_settings")
