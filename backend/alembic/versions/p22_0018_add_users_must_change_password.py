"""Add users.must_change_password

Revision ID: p22_0018
Revises: p22_0017

First half of a two-step rollout (expand, then use). The column says "this
person must set their own password before doing anything else", used for an
account that Elevare provisioned with a temporary password.

This release adds the column only. Nothing reads it yet and the ``User`` model is
deliberately not changed, so the running code never selects a column that may not
exist yet while this migration is still running after the containers are up. The
code that uses it ships in the next release.

Safe on the live ``users`` table: a column with a constant default is a
metadata-only change on PostgreSQL 11 and later (production runs 16), so there is
no table rewrite, and every existing user gets ``false``.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0018"
down_revision: str | None = "p22_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
