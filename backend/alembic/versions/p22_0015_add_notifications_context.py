"""Add context to notifications

Revision ID: p22_0015
Revises: p22_0014

Lets a notification carry structured data its action needs beyond a
single (entity_type, entity_id) link — e.g. AI_INTERVIEW_RESET_REQUEST
needs both a job_id and a talent_pool_profile_id so the recipient can
resend the invite directly from the notification.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0015"
down_revision: str | None = "p22_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "context")
