"""Add Paystack recurring-billing fields

Revision ID: p22_0016
Revises: p22_0015

Phase 4 of the subscription-payment gap review (docs/subscription-
payment-architecture-review.md): switching from one-off "Initialize
Transaction" charges to real Paystack Subscription objects, so renewals
actually auto-charge instead of silently never happening.

- plans.provider_plan_code: the Paystack Plan this maps to (set once per
  paid plan, either via the Paystack dashboard or a one-off script —
  requires live Paystack credentials, so it isn't done in this migration).
- payments.provider_customer_code: Paystack's stable per-customer
  identifier, captured off the first successful charge. This is how the
  subscription.create webhook (which carries no metadata of ours) gets
  correlated back to an organization.
- subscriptions.provider_customer_code / provider_email_token: needed
  together with the existing provider_subscription_id to actually cancel a
  subscription on Paystack's side (POST /subscription/disable needs both
  `code` and a separate `token`, not the same value twice).
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0016"
down_revision: str | None = "p22_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans", sa.Column("provider_plan_code", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "payments",
        sa.Column("provider_customer_code", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_customer_code", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("provider_email_token", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "provider_email_token")
    op.drop_column("subscriptions", "provider_customer_code")
    op.drop_column("payments", "provider_customer_code")
    op.drop_column("plans", "provider_plan_code")
