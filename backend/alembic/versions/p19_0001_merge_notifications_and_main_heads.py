"""Merge p18_0001 (notifications) and f9a3c7e1b2d4 (main) heads.

Revision ID: p19_0001
Revises: f9a3c7e1b2d4, p18_0001
Create Date: 2026-07-22 00:00:00.000000
"""

from typing import Sequence, Union

revision: str = "p19_0001"
down_revision: Union[str, Sequence[str], None] = ("f9a3c7e1b2d4", "p18_0001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
