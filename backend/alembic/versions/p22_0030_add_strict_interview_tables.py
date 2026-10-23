"""Add interview_strict_runs and interview_turns: the state of a strict, text-question interview

Revision ID: p22_0030
Revises: p22_0029

``interview_strict_runs`` has one row per interview that uses the strict style (the style is
decided when the invite is created; an interview with no row here is the existing live
interview). It holds the rules the candidate accepted (version and time) and a copy of the
job's questions taken when the interview starts, so editing the job's list later never
changes an interview that has begun. ``interview_turns`` has one row per question or
follow-up the candidate was shown, with the time it was shown and the text of the answer.

Safe on the live database: two brand-new tables and no change to ``interviews``. That is
deliberate: a new column on ``interviews`` would break every interview query between the
new containers starting and this migration finishing. The old code never looks at either
table. (docs/08_DECISIONS.md, "The new strict, text-only AI interview", item 24.)
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0030"
down_revision: str | None = "p22_0029"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "interview_strict_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rules_version", sa.String(20), nullable=True),
        sa.Column("rules_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("questions", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("interview_id", name="uq_interview_strict_runs_interview"),
    )

    op.create_table(
        "interview_turns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("time_limit_seconds", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("answer_seconds", sa.Float(), nullable=True),
        sa.UniqueConstraint("interview_id", "position", name="uq_interview_turns_position"),
    )
    op.create_index("ix_interview_turns_interview_id", "interview_turns", ["interview_id"])


def downgrade() -> None:
    op.drop_index("ix_interview_turns_interview_id", table_name="interview_turns")
    op.drop_table("interview_turns")
    op.drop_table("interview_strict_runs")
