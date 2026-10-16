"""Add an index on credit_transactions.reference_id

Revision ID: p22_0019
Revises: p22_0018

An AI interview's charge and refund rows are found by the interview's id, which is
stored in ``reference_id``: on every invite, to see whether the interview is
already paid, and in the hourly sweep that refunds invites which expired unopened.
Without an index each of those lookups reads the whole ledger.

Safe on the live database: an index changes no data or columns, so code that does
not know about it is unaffected while the migration runs after the containers are
up. ``credit_transactions`` is small (a row per credit movement), so the build is
over in moments and its brief write lock is not noticeable.
"""

from alembic import op

revision: str = "p22_0019"
down_revision: str | None = "p22_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_credit_transactions_reference_id",
        "credit_transactions",
        ["reference_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_transactions_reference_id", table_name="credit_transactions")
