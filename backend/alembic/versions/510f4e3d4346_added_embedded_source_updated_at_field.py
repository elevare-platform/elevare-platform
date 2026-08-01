"""added_embedded_source_updated_at_field

Revision ID: 510f4e3d4346
Revises: p20_0001
Create Date: 2026-07-31 19:15:48.821023

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '510f4e3d4346'
down_revision: Union[str, None] = 'p20_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("candidate_profile", sa.Column("embedding_source_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("talent_pool_profiles", sa.Column("embedding_source_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("jobs", sa.Column("embedding_source_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "embedding_source_updated_at")
    op.drop_column("talent_pool_profiles", "embedding_source_updated_at")
    op.drop_column("candidate_profile", "embedding_source_updated_at")

