"""Add job_interview_questions: a job's list of strict-interview questions

Revision ID: p22_0029
Revises: p22_0028

One row per question of a job's strict interview (docs/08_DECISIONS.md, "The new strict,
text-only AI interview"). The list is the same for every candidate; the AI drafts it from the
job's interview brief and the employer edits it. ``position`` is unique per job, so two
requests saving the list at the same moment cannot interleave their rows.

Safe on the live database: a brand-new table that nothing else references, so no existing
row or query is affected, and the old code never looks at it.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0029"
down_revision: str | None = "p22_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_interview_questions",
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
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(10), nullable=False, server_default="EMPLOYER"),
        sa.UniqueConstraint("job_id", "position", name="uq_job_interview_questions_position"),
    )
    op.create_index(
        "ix_job_interview_questions_job_id", "job_interview_questions", ["job_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_job_interview_questions_job_id", table_name="job_interview_questions")
    op.drop_table("job_interview_questions")
