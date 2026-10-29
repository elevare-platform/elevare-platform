"""Add the per-job switches for the score number, the gaps and risks and the written assessment

Revision ID: p22_0045
Revises: p22_0044

Three new columns on ``job_score_visibility`` (docs/08_DECISIONS.md, item 61): ``show_score_number``
(false hides the total and the points but keeps the band and the 1 to 5 ratings), ``show_gaps`` (false
hides the gaps and risks) and ``show_writeup`` (false hides the written assessment text). A job with no
row, or a row made before this, shows all three, as every job did.

Safe on the live database: ``job_score_visibility`` is a small table of its own, the columns are NOT NULL
with a constant default (no table rewrite, every existing row reads true), and the only code that reads
them is guarded for the seconds before this runs.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0045"
down_revision: str | None = "p22_0044"
branch_labels = None
depends_on = None

COLUMNS = ("show_score_number", "show_gaps", "show_writeup")


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column(
            "job_score_visibility",
            sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    for name in reversed(COLUMNS):
        op.drop_column("job_score_visibility", name)
