"""Add the record of an interview being scored again

Revision ID: p22_0046
Revises: p22_0045

One new table (docs/08_DECISIONS.md, item 62): ``interview_rescores``, one row per interview that an
Elevare admin has asked to be scored again, holding whether that is PENDING, FAILED or DONE, who asked,
when, and why it failed. The review window uses it to show "scoring again" (and hide the earlier result
until the new one is in) and to say plainly when it did not work.

Safe on the live database: a new table of its own, nothing existing is changed, and the only code that
reads it is guarded for the seconds before this runs.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0046"
down_revision: str | None = "p22_0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_rescores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(300), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("interview_rescores")
