"""Add ai_score_failure to talent_pool_profiles and applications

Revision ID: p22_0021
Revises: p22_0020

First half of a two-step rollout (expand, then use). When a candidate could not be
scored, the row says why instead of holding a fake score of 0:

- ``CV_UNREADABLE``: nothing could be read from the CV, so no scoring was attempted.
- ``SCORING_FAILED``: the scoring call failed or returned no usable score; it can be
  tried again.

NULL means nothing is wrong (scored, or not scored yet).

This release adds the columns only. Nothing reads or writes them yet and the
``TalentPoolProfiles`` and ``Application`` models are deliberately not changed, so
the running code never selects a column that may not exist yet while this migration
is still running after the containers are up. The code that uses them ships in the
next release.

Safe on the live tables: a nullable column with no default is a metadata-only change
in PostgreSQL (no table rewrite, no long lock), and every existing row gets NULL.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0021"
down_revision: str | None = "p22_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "talent_pool_profiles",
        sa.Column("ai_score_failure", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "applications",
        sa.Column("ai_score_failure", sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applications", "ai_score_failure")
    op.drop_column("talent_pool_profiles", "ai_score_failure")
