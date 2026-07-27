"""added_match_notifications_table

Revision ID: d63aa06ba055
Revises: p19_0001
Create Date: 2026-07-22 10:30:12.781326

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d63aa06ba055"
down_revision: Union[str, None] = "p19_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "match_notifications",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("candidate_profile_id", sa.UUID(), nullable=True),
        sa.Column("talent_pool_profile_id", sa.UUID(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column(
            "is_new",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["candidate_profile_id"], ["candidate_profile.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["talent_pool_profile_id"],
            ["talent_pool_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_match_notifications_is_new",
        "match_notifications",
        ["job_id", "is_new"],
        unique=False,
    )
    op.create_index(
        "ix_match_notifications_job_id",
        "match_notifications",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_match_notifications_is_new", table_name="match_notifications")
    op.drop_index("ix_match_notifications_job_id", table_name="match_notifications")
    op.drop_table("match_notifications")
