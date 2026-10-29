"""Add the per-job switch for the scorecard's Evaluation Summary

Revision ID: p22_0044
Revises: p22_0043

One new column on ``job_score_visibility`` (docs/08_DECISIONS.md, item 57): ``show_summary``, false for
a job whose scorecard is to be printed without its Evaluation Summary (the practical case rating, the
strengths and the human decision). A job with no row, or a row made before this, shows it, as every
job did.

Safe on the live database: ``job_score_visibility`` is a small table of its own, the column is NOT NULL
with a constant default (no table rewrite, every existing row reads true), and the only code that reads
it is guarded for the seconds before this runs.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0044"
down_revision: str | None = "p22_0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_score_visibility",
        sa.Column("show_summary", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("job_score_visibility", "show_summary")
