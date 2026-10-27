"""Add the answer time of a follow-up to a question

Revision ID: p22_0035
Revises: p22_0034

One nullable column on a table that only this branch introduced (docs/08_DECISIONS.md, item 41):
``job_interview_questions.follow_up_seconds``, how long a candidate has to answer a follow-up on
that question. NULL means the platform default (90 seconds), which is what every question had
before. The table is new in p22_0029, so no live row is rewritten.

Safe on the live database: nothing existing is changed for the old code.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0035"
down_revision: str | None = "p22_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("job_interview_questions", sa.Column("follow_up_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_interview_questions", "follow_up_seconds")
