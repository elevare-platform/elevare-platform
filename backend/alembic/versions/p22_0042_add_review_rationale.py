"""Add an admin's edited written assessment to an interview's score review

Revision ID: p22_0042
Revises: p22_0041

One new nullable column, ``interview_score_reviews.rationale`` (docs/08_DECISIONS.md, item 55): the
written assessment an Elevare admin wrote in place of the system's text for an interview. Empty means
the system's own text is shown. The system's text (``interviews.ai_rationale``) is never overwritten.

Safe on the live database: a nullable column with no default is added without rewriting the table
(which holds only the few reviews that have been made), and the code that reads reviews is guarded
for the seconds before this runs.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0042"
down_revision: str | None = "p22_0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_score_reviews", sa.Column("rationale", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_score_reviews", "rationale")
