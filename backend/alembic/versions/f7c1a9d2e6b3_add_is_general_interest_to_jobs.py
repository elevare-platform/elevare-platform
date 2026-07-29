"""add_is_general_interest_to_jobs

Revision ID: f7c1a9d2e6b3
Revises: d63aa06ba055
Create Date: 2026-07-27 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7c1a9d2e6b3"
down_revision: Union[str, None] = "d63aa06ba055"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column(
            "is_general_interest",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("jobs", "is_general_interest")
