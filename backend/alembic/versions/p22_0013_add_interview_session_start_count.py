"""Add session_start_count to interviews

Revision ID: p22_0013
Revises: p22_0012

Tracks how many times a live Realtime session has actually been minted
for an interview, so a candidate reloading mid-interview after hearing
the AI's opening question can't get unlimited fresh attempts — one
restart is tolerated, a second is blocked. See
InterviewService._start_session.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0013"
down_revision: str | None = "p22_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column(
            "session_start_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("interviews", "session_start_count")
