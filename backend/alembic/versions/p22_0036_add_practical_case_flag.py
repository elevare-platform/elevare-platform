"""Mark a question as the interview's practical case

Revision ID: p22_0036
Revises: p22_0035

One column with a default on a table that only this branch introduced (docs/08_DECISIONS.md, item
43): ``job_interview_questions.is_practical``, true for the question that is the interview's
practical case (scored separately out of 5). ``NOT NULL DEFAULT false`` is safe here: the table is
new in p22_0029, and adding a column with a constant default does not rewrite the table.

Safe on the live database: nothing existing is changed for the old code.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0036"
down_revision: str | None = "p22_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_interview_questions",
        sa.Column("is_practical", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("job_interview_questions", "is_practical")
