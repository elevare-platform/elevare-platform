"""add_embedding_columns_to_talent_pool_profiles

Revision ID: p12_0003
Revises: p12_0002
Create Date: 2026-07-02

"""
from typing import Union

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = 'p12_0003'
down_revision: Union[str, None] = 'p12_0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('talent_pool_profiles', sa.Column('profile_embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True))
    op.add_column('talent_pool_profiles', sa.Column('embedding_source_hash', sa.String(length=64), nullable=True))
    op.add_column('talent_pool_profiles', sa.Column('embedding_generated_at', sa.DateTime(timezone=True), nullable=True))
    op.execute(
        "CREATE INDEX ON talent_pool_profiles USING ivfflat (profile_embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS talent_pool_profiles_profile_embedding_idx")
    op.drop_column('talent_pool_profiles', 'embedding_generated_at')
    op.drop_column('talent_pool_profiles', 'embedding_source_hash')
    op.drop_column('talent_pool_profiles', 'profile_embedding')
