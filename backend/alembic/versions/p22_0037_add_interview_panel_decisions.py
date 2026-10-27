"""Add the hiring panel's decision on an interview

Revision ID: p22_0037
Revises: p22_0036

One new table (docs/08_DECISIONS.md, item 44): ``interview_panel_decisions``, the human panel's
decision about a candidate after an interview (strong shortlist, shortlist, hold or do not
shortlist), its rationale and who signed it off. Append-only. A table of its own, so ``interviews``
is untouched.

Safe on the live database: nothing existing is changed for the old code.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0037"
down_revision: str | None = "p22_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_panel_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "interview_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("interviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_by_name", sa.String(200), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_interview_panel_decisions_interview", "interview_panel_decisions", ["interview_id", "decided_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_interview_panel_decisions_interview", table_name="interview_panel_decisions")
    op.drop_table("interview_panel_decisions")
