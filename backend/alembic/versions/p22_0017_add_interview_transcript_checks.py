"""Add interview_transcript_checks table

Revision ID: p22_0017
Revises: p22_0016

Holds the server-side transcription of an interview recording and how it
compared with the transcript the candidate's browser submitted. A new table
(additive, no change to ``interviews``), so it is safe on the live database
and code that does not read it is unaffected while the migration runs.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0017"
down_revision: str | None = "p22_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_transcript_checks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("interview_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("server_transcript", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "interview_id", name="uq_interview_transcript_checks_interview"
        ),
    )


def downgrade() -> None:
    op.drop_table("interview_transcript_checks")
