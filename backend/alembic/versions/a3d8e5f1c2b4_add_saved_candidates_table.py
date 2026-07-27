"""add_saved_candidates_table

Revision ID: a3d8e5f1c2b4
Revises: f7c1a9d2e6b3
Create Date: 2026-07-27 00:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3d8e5f1c2b4"
down_revision: Union[str, None] = "f7c1a9d2e6b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_candidates",
        sa.Column("employer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "talent_pool_profile_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employer_id", "talent_pool_profile_id", name="uq_saved_candidate"
        ),
    )
    op.create_index(
        "ix_saved_candidates_employer_id", "saved_candidates", ["employer_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_saved_candidates_employer_id", table_name="saved_candidates")
    op.drop_table("saved_candidates")
