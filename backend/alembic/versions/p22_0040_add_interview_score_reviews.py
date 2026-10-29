"""Add an Elevare reviewer's score for an interview

Revision ID: p22_0040
Revises: p22_0039

One new table (docs/08_DECISIONS.md, item 52): ``interview_score_reviews``, the score an Elevare admin
sets for a finished interview in place of the one the system worked out, with who set it, when, an
optional reason, and the system's own score and band at that moment. Append-only: the latest row is
the one shown, and a row with neither a score nor changed ratings takes the review away again. A table of its own, so
``interviews`` is untouched.

Safe on the live database: a new table, nothing existing is changed for the old code, and only the new
code reads it.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0040"
down_revision: str | None = "p22_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_score_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        # The competency ratings the reviewer changed, as {competency name: 1 to 5}; only those that
        # differ from the system's own. Empty or null when only the total was set.
        sa.Column("ratings", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_by_name", sa.String(200), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("original_score", sa.Integer(), nullable=True),
        sa.Column("original_band", sa.String(30), nullable=True),
    )
    op.create_index(
        "ix_interview_score_reviews_interview", "interview_score_reviews", ["interview_id", "reviewed_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_interview_score_reviews_interview", table_name="interview_score_reviews")
    op.drop_table("interview_score_reviews")
