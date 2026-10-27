"""Add job scoring profiles, weighted interview scores, and the optional competency on a question

Revision ID: p22_0033
Revises: p22_0032

Two new tables and one nullable column on a table that only this branch introduced
(docs/08_DECISIONS.md, item 36):

* ``job_scoring_profiles``: a job's competencies with weights, its key competencies and its band
  thresholds. A table of its own, NOT a column on ``jobs``: a new column on ``jobs`` would break
  every job query between the new containers starting and this migration finishing.
* ``interview_weighted_scores``: the weighted score report of an interview scored with a profile.
  Likewise its own table, so ``interviews`` is untouched.
* ``job_interview_questions.competency``: which competency a question was written to test.
  Nullable, and the table is new in p22_0029, so no live row is rewritten.

Safe on the live database: nothing existing is changed for the old code.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0033"
down_revision: str | None = "p22_0032"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "job_scoring_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("competencies", postgresql.JSONB(), nullable=False),
        sa.Column("bands", postgresql.JSONB(), nullable=False),
        sa.Column("key_min_rating", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("template_code", sa.String(40), nullable=True),
        sa.UniqueConstraint("job_id", name="uq_job_scoring_profiles_job"),
    )
    op.create_table(
        "interview_weighted_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("report", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("interview_id", name="uq_interview_weighted_scores_interview"),
    )
    op.add_column("job_interview_questions", sa.Column("competency", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("job_interview_questions", "competency")
    op.drop_table("interview_weighted_scores")
    op.drop_table("job_scoring_profiles")
