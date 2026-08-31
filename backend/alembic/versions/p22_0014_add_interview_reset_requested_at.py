"""Add reset_requested_at to interviews

Revision ID: p22_0014
Revises: p22_0013

Tracks when a candidate locked out by the restart lock asked the
employer to reset it, so the "request reset" endpoint can no-op on a
repeat click instead of spamming the employer. Cleared when the
employer actually resends the invite (create_invite). See
InterviewService._request_reset.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0014"
down_revision: str | None = "p22_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "interviews",
        sa.Column("reset_requested_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interviews", "reset_requested_at")
