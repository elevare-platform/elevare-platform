"""Add override_email to talent_pool_profiles

Revision ID: p22_0009
Revises: p22_0008

Sourced-only candidates only have an email if the AI CV-parsing pipeline
managed to extract one, which fails for sparse or malformed CVs — leaving
the employer unable to invite them to an AI interview. This adds a nullable
employer-entered override that resolve_candidate_email() checks after the
self-registered candidate_profile.user.email path but before the
auto-parsed one, so an employer can manually fix a missing/wrong email
without it being silently overwritten by a future CV re-parse.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0009"
down_revision: str | None = "p22_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "talent_pool_profiles",
        sa.Column("override_email", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("talent_pool_profiles", "override_email")
