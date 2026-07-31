"""add resume_page_token to ingestion_import_runs

Revision ID: p20_0001
Revises: f1ca5d013180
Create Date: 2026-07-31 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p20_0001"
down_revision: Union[str, None] = "f1ca5d013180"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ingestion_import_runs",
        sa.Column("resume_page_token", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ingestion_import_runs", "resume_page_token")
