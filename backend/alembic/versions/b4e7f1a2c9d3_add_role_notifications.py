"""add_role_notifications

Revision ID: b4e7f1a2c9d3
Revises: a90a457e7f79
Create Date: 2026-07-20 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e7f1a2c9d3"
down_revision: Union[str, None] = "a90a457e7f79"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "role_notifications",
        sa.Column("employer_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("talent_pool_profile_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["employer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["talent_pool_profile_id"], ["talent_pool_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "employer_id",
            "job_id",
            "talent_pool_profile_id",
            name="uq_role_notification",
        ),
    )
    op.create_index(
        op.f("ix_role_notifications_employer_id"),
        "role_notifications",
        ["employer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_notifications_job_id"),
        "role_notifications",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_role_notifications_talent_pool_profile_id"),
        "role_notifications",
        ["talent_pool_profile_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_role_notifications_talent_pool_profile_id"),
        table_name="role_notifications",
    )
    op.drop_index(op.f("ix_role_notifications_job_id"), table_name="role_notifications")
    op.drop_index(
        op.f("ix_role_notifications_employer_id"), table_name="role_notifications"
    )
    op.drop_table("role_notifications")
