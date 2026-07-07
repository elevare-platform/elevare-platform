"""add status and reviewed_at to testimonials

Revision ID: cd5ec87a801b
Revises: 676964ce415d
Create Date: 2026-07-07 11:39:14.373576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd5ec87a801b'
down_revision: Union[str, None] = '676964ce415d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    testimonialstatus = sa.Enum('pending', 'approved', 'rejected', name='testimonialstatus')
    testimonialstatus.create(op.get_bind(), checkfirst=True)
    op.add_column('testimonials', sa.Column('status', testimonialstatus, server_default='pending', nullable=False))
    op.add_column('testimonials', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('testimonials', 'reviewed_at')
    op.drop_column('testimonials', 'status')
    op.execute("DROP TYPE IF EXISTS testimonialstatus")
