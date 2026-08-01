"""add job moderation_reason

Revision ID: 34a46ce1dbe3
Revises: 510f4e3d4346
Create Date: 2026-08-01 10:55:59.483532

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '34a46ce1dbe3'
down_revision: Union[str, None] = '510f4e3d4346'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('moderation_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'moderation_reason')
