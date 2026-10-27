"""Add the company's saved sets of interview questions

Revision ID: p22_0038
Revises: p22_0037

One new table (docs/08_DECISIONS.md, item 46): ``interview_question_templates``, the sets of
questions a company saves to use again (questions, probes, times, practical case, follow-up choice
and, optionally, the scoring profile). Owned by the company, one name per company whatever its case.
A table of its own, so nothing existing is touched.

Safe on the live database: nothing existing is changed for the old code.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0038"
down_revision: str | None = "p22_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_question_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("scoring_profile", postgresql.JSONB(), nullable=True),
        sa.Column("follow_up_mode", sa.String(12), nullable=False, server_default="STANDARD"),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_by_name", sa.String(200), nullable=False),
    )
    op.create_index(
        "ix_interview_question_templates_organization_id", "interview_question_templates", ["organization_id"]
    )
    op.create_index(
        "uq_interview_question_templates_org_name",
        "interview_question_templates",
        ["organization_id", sa.text("lower(name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_interview_question_templates_org_name", table_name="interview_question_templates")
    op.drop_index("ix_interview_question_templates_organization_id", table_name="interview_question_templates")
    op.drop_table("interview_question_templates")
