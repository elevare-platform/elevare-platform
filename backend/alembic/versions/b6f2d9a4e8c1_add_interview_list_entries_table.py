"""add_interview_list_entries_table

Revision ID: b6f2d9a4e8c1
Revises: a3d8e5f1c2b4
Create Date: 2026-07-27 00:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6f2d9a4e8c1"
down_revision: Union[str, None] = "a3d8e5f1c2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "interview_list_entries",
        sa.Column("employer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "talent_pool_profile_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
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
        sa.ForeignKeyConstraint(["employer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["talent_pool_profile_id"], ["talent_pool_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employer_id",
            "talent_pool_profile_id",
            "job_id",
            name="uq_interview_list_entry",
        ),
    )
    op.create_index(
        "ix_interview_list_entries_job_id", "interview_list_entries", ["job_id"]
    )
    op.create_index(
        "ix_interview_list_entries_employer_id",
        "interview_list_entries",
        ["employer_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_interview_list_entries_employer_id", table_name="interview_list_entries"
    )
    op.drop_index(
        "ix_interview_list_entries_job_id", table_name="interview_list_entries"
    )
    op.drop_table("interview_list_entries")
