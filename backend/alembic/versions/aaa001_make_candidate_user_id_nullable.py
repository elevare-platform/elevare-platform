"""make_candidate_profile_user_id_nullable

Revision ID: aaa001
Revises: 94cb6946e696
Create Date: 2026-06-16

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'aaa001'
down_revision: Union[str, None] = '94cb6946e696'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('candidate_profile', 'user_id', nullable=True)


def downgrade() -> None:
    op.alter_column('candidate_profile', 'user_id', nullable=False)
