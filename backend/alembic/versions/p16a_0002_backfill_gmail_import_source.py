"""backfill gmail_import source for talent pool profiles sourced via ingestion

Revision ID: p16a_0002
Revises: p16a_0001
Create Date: 2026-07-11 00:00:00.000000

Background:
    Phase 16A introduced Gmail ingestion. Initial imports stored source='email'
    before the 'gmail_import' SourceType was introduced. This migration
    backfills those rows so they are correctly identified as Gmail imports.

    A talent pool profile was created by Gmail ingestion if:
      - source = 'email'
      - source_note LIKE 'Gmail import%'
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "p16a_0002"
down_revision: Union[str, None] = "p16a_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE talent_pool_profiles
        SET source = 'gmail_import'
        WHERE source = 'email'
          AND source_note LIKE 'Gmail import%'
    """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE talent_pool_profiles
        SET source = 'email'
        WHERE source = 'gmail_import'
          AND source_note LIKE 'Gmail import%'
    """
    )
