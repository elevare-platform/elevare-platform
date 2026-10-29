"""Add an admin's hand-filled scorecard fields to an interview's score review

Revision ID: p22_0043
Revises: p22_0042

One new nullable column, ``interview_score_reviews.scorecard`` (docs/08_DECISIONS.md, item 56): what an
Elevare admin filled in by hand on the interview scorecard in place of the system's: the text of each
competency's Evidence / Verification, the practical case rating, the strengths and the human decision
wording. Empty means the system's own are shown.

Safe on the live database: a nullable column with no default is added without rewriting the table
(which holds only the few reviews that have been made), and the code that reads reviews is guarded
for the seconds before this runs.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0043"
down_revision: str | None = "p22_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_score_reviews", sa.Column("scorecard", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("interview_score_reviews", "scorecard")
