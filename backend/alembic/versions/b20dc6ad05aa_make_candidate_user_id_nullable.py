"""make_candidate_user_id_nullable

Revision ID: b20dc6ad05aa
Revises: 091df3dcdcb3
Create Date: 2026-06-14 18:12:27.950565

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b20dc6ad05aa'
down_revision: Union[str, None] = '091df3dcdcb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'candidate_profile', 'user_id', nullable=True
    )


def downgrade() -> None:
    op.alter_column(
        'candidate_profile', 'user_id', nullable=False
    )
