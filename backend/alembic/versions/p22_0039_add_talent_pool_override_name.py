"""Add an employer-entered name to a sourced candidate

Revision ID: p22_0039
Revises: p22_0038

One new nullable column, ``talent_pool_profiles.override_name`` (docs/08_DECISIONS.md, item 50): the
name an employer types when the name read from a CV is wrong. It is used in place of the name read
from the CV; the CV itself is not changed. Same idea as ``override_email``.

Safe on the live database: a nullable column with no default is added without rewriting the table,
and nothing reads it until the code that maps it is deployed (a second step, after this one has
run), so the old code is unaffected.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0039"
down_revision: str | None = "p22_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("talent_pool_profiles", sa.Column("override_name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("talent_pool_profiles", "override_name")
