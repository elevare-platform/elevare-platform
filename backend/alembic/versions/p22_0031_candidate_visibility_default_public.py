"""New candidate profiles are visible to employers by default

Revision ID: p22_0031
Revises: p22_0030

Changes only the database DEFAULT of ``candidate_profile.visibility`` from APPLIED_ONLY to
PUBLIC, for rows inserted from now on without a value. Every existing row keeps what it has:
nobody's visibility changes without them choosing it. The profile page tells a candidate that
employers can find them and that they can change it any time (docs/08_DECISIONS.md, item 34).

Safe on the live database: no rewrite and no lock beyond a catalog change. The application also
sets PUBLIC itself when it creates a profile, so the seconds between the new containers starting
and this migration finishing behave the same.
"""

from alembic import op

revision: str = "p22_0031"
down_revision: str | None = "p22_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("candidate_profile", "visibility", server_default="PUBLIC")


def downgrade() -> None:
    op.alter_column("candidate_profile", "visibility", server_default="APPLIED_ONLY")
