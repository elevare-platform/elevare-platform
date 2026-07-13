"""add structured job description fields

Revision ID: a1b2c3d4e5f6
Revises: 676964ce415d
Create Date: 2026-07-12 00:00:00.000000

Adds 7 structured description fields to the jobs table and makes the legacy
``description`` column nullable so existing production jobs are untouched.
New jobs will populate the structured fields and leave ``description`` as NULL.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "p16b_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make legacy description nullable — existing rows keep their data intact
    op.alter_column("jobs", "description", existing_type=sa.Text(), nullable=True)

    # Add structured description columns (all nullable — old jobs won't have them)
    op.add_column("jobs", sa.Column("about_the_role", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("key_responsibilities", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("requirements", sa.Text(), nullable=True))
    op.add_column(
        "jobs", sa.Column("preferred_certifications", sa.Text(), nullable=True)
    )
    op.add_column("jobs", sa.Column("technical_competencies", sa.Text(), nullable=True))
    op.add_column("jobs", sa.Column("what_we_offer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "what_we_offer")
    op.drop_column("jobs", "technical_competencies")
    op.drop_column("jobs", "preferred_certifications")
    op.drop_column("jobs", "requirements")
    op.drop_column("jobs", "key_responsibilities")
    op.drop_column("jobs", "about_the_role")

    # Restore description to NOT NULL (only safe if all rows still have a value)
    op.alter_column("jobs", "description", existing_type=sa.Text(), nullable=False)
