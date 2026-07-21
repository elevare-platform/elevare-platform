"""merge_kyc_and_monetization_heads

Merges two migrations that both branched off a90a457e7f79:
- b4e7f1a2c9d3 (role_notifications, this branch)
- e3f1a2b4c5d6 (KYC, from develop/main)

No-op — both sides are purely additive and don't touch the same tables.

Revision ID: f9a3c7e1b2d4
Revises: b4e7f1a2c9d3, e3f1a2b4c5d6
Create Date: 2026-07-20 00:00:00.000000
"""

from typing import Sequence, Union

revision: str = "f9a3c7e1b2d4"
down_revision: Union[str, Sequence[str], None] = ("b4e7f1a2c9d3", "e3f1a2b4c5d6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
