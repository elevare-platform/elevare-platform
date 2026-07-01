"""add_ivfflat_indexes_to_embedding_columns

Revision ID: p12_0002
Revises: 7af353621b03
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'p12_0002'
down_revision: Union[str, None] = '7af353621b03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # lists=100 is a reasonable starting value for current scale.
    # Tune upward as row count grows (rule of thumb: lists ≈ sqrt(rows)).
    op.execute(
        "CREATE INDEX ON candidate_profile USING ivfflat (profile_embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.execute(
        "CREATE INDEX ON jobs USING ivfflat (job_embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS candidate_profile_profile_embedding_idx")
    op.execute("DROP INDEX IF EXISTS jobs_job_embedding_idx")
