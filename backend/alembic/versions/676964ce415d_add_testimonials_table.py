"""add testimonials table

Revision ID: 676964ce415d
Revises: p12_0003
Create Date: 2026-07-07 10:09:42.918093

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '676964ce415d'
down_revision: Union[str, None] = 'p12_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'testimonials',
        sa.Column('full_name', sa.String(length=150), nullable=False),
        sa.Column('company', sa.String(length=150), nullable=True),
        sa.Column('position', sa.String(length=150), nullable=True),
        sa.Column('testimony', sa.Text(), nullable=False),
        sa.Column('image', sa.String(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('testimonials')
