"""Add the plan credit allowance columns and set Professional's allowance

Revision ID: p22_0020
Revises: p22_0019

First half of a two-step rollout (expand, then use). A paid plan will include a
monthly allowance of credits that resets at each renewal, kept apart from the
credits an organization buys, which never expire:

- ``employer_credits.plan_balance``: the plan credits an organization has left
  this period (``balance`` stays the bought credits).
- ``credit_transactions.plan_portion``: how much of a spend or refund came from the
  plan credits, so a refund returns to the pot it was taken from.
- ``plans.included_credits`` is set to 40 for Professional. Starter stays empty
  (nothing included), Enterprise is set per contract.

This release adds the columns and the number only. Nothing reads them yet and the
``EmployerCredits`` and ``CreditTransaction`` models are deliberately not changed,
so the running code never selects a column that may not exist yet while this
migration is still running after the containers are up. The code that uses them
ships in the next release.

Safe on the live tables: a column with a constant default is a metadata-only change
on PostgreSQL 11 and later (production runs 16), so there is no table rewrite and
every existing row gets 0. ``employer_credits`` has one row per organization, so
checking the new constraint is instant. The plan update only fills a value that is
still empty, so it never overwrites an allowance someone set by hand.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0020"
down_revision: str | None = "p22_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "employer_credits",
        sa.Column("plan_balance", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_employer_credits_plan_balance_non_negative",
        "employer_credits",
        "plan_balance >= 0",
    )
    op.add_column(
        "credit_transactions",
        sa.Column("plan_portion", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        "UPDATE plans SET included_credits = 40 "
        "WHERE code = 'professional' AND included_credits IS NULL"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE plans SET included_credits = NULL "
        "WHERE code = 'professional' AND included_credits = 40"
    )
    op.drop_column("credit_transactions", "plan_portion")
    op.drop_constraint(
        "ck_employer_credits_plan_balance_non_negative",
        "employer_credits",
        type_="check",
    )
    op.drop_column("employer_credits", "plan_balance")
