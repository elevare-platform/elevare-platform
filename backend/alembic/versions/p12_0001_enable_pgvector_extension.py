"""enable_pgvector_extension

Revision ID: p12_0001
Revises: e046b6082572
Create Date: 2026-06-30

"""
from typing import Union
from alembic import op

revision: str = 'p12_0001'
down_revision: Union[str, None] = 'e046b6082572'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
