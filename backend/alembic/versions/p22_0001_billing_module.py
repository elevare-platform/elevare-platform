"""Billing module — plans, subscriptions, payments, webhook_events, and the credits FK repoint

Revision ID: p22_0001
Revises: p21_0001
Create Date: 2026-08-10 00:00:00.000000

Part of the subscription/payment work (see
docs/subscription-payment-architecture-review.md, Phase 1). Adds the four
new billing tables and repoints `employer_credits`/`credit_transactions`
from `users.id` to `organizations.id` (finding #7) — credits become a
shared company wallet now that `Organization` exists (Phase 1a). Seeds
the Starter/Professional plan catalog; Enterprise stays sales-negotiated
per the pricing page, no self-serve row needed.

Safety notes:
    - There is no live subscription/payment data to migrate around — the
      four new tables are purely additive.
    - The credits FK repoint changes what `employer_id` points at, not
      its type (both are UUID) or its nullability — a plain
      drop-constraint/add-constraint, no backfill needed since every
      existing `employer_credits`/`credit_transactions` row currently
      keys off a `users.id` that, post Phase 1a, is 1:1 reachable via
      that user's `organization_id`. Rows are updated to point at the
      owning organization before the constraint is added.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0001"
down_revision: str | None = "p21_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- 1. plans ---------------------------------------------------------
    op.create_table(
        "plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_kobo", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("interval", sa.String(10), nullable=False),
        sa.Column("job_posting_limit", sa.Integer(), nullable=True),
        sa.Column("included_credits", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("price_kobo >= 0", name="ck_plans_price_non_negative"),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )

    # -- 2. subscriptions ---------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("organization_id", name="uq_subscriptions_organization_id"),
    )
    op.create_index(
        "ix_subscriptions_provider_subscription_id",
        "subscriptions",
        ["provider_subscription_id"],
    )

    # -- 3. payments ----------------------------------------------------------
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("amount_kobo", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=False),
        sa.Column("credits_granted", sa.Integer(), nullable=True),
        sa.Column("initiated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount_kobo >= 0", name="ck_payments_amount_non_negative"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("provider_reference", name="uq_payments_provider_reference"),
    )
    op.create_index("ix_payments_organization_id", "payments", ["organization_id"])
    op.create_index("ix_payments_provider_reference", "payments", ["provider_reference"])

    # -- 4. webhook_events ------------------------------------------------
    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "provider", "provider_event_id", name="uq_webhook_events_provider_event"
        ),
    )

    # -- 5. seed the plan catalog -------------------------------------------
    # Enterprise is sales-negotiated (pricing page: "Contact Sales") — no
    # self-serve row, matches admin-comp-only handling in a later phase.
    plans_table = sa.table(
        "plans",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("price_kobo", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("interval", sa.String),
        sa.column("job_posting_limit", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("sort_order", sa.Integer),
    )
    op.bulk_insert(
        plans_table,
        [
            {
                "id": uuid.uuid4(),
                "code": "starter",
                "name": "Starter",
                "description": "Free plan for getting started — up to 3 active job postings.",
                "price_kobo": 0,
                "currency": "NGN",
                "interval": "MONTHLY",
                "job_posting_limit": 3,
                "is_active": True,
                "sort_order": 0,
            },
            {
                "id": uuid.uuid4(),
                "code": "professional",
                "name": "Professional",
                "description": "Unlimited active job postings and priority candidate matching.",
                "price_kobo": 0,
                "currency": "NGN",
                "interval": "MONTHLY",
                "job_posting_limit": None,
                "is_active": True,
                "sort_order": 1,
            },
        ],
    )

    # -- 6. credits FK repoint: users.id -> organizations.id -----------------
    # Drop the old users.id-pointing constraints first — the data rewrite
    # below sets employer_id to an organization id, which the old
    # constraint would reject mid-flight.
    op.drop_constraint("employer_credits_employer_id_fkey", "employer_credits", type_="foreignkey")
    op.drop_constraint("credit_transactions_employer_id_fkey", "credit_transactions", type_="foreignkey")

    # Point every existing employer_credits/credit_transactions row at its
    # owning organization (reachable via the Phase 1a organization_id column
    # on users).
    op.execute(
        """
        UPDATE employer_credits ec
        SET employer_id = u.organization_id
        FROM users u
        WHERE ec.employer_id = u.id AND u.organization_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE credit_transactions ct
        SET employer_id = u.organization_id
        FROM users u
        WHERE ct.employer_id = u.id AND u.organization_id IS NOT NULL
        """
    )
    op.create_foreign_key(
        "employer_credits_employer_id_fkey",
        "employer_credits",
        "organizations",
        ["employer_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "credit_transactions_employer_id_fkey",
        "credit_transactions",
        "organizations",
        ["employer_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # -- reverse 6: credits FK back to users.id -----------------------------
    op.drop_constraint("credit_transactions_employer_id_fkey", "credit_transactions", type_="foreignkey")
    op.drop_constraint("employer_credits_employer_id_fkey", "employer_credits", type_="foreignkey")
    op.execute(
        """
        UPDATE employer_credits ec
        SET employer_id = u.id
        FROM users u
        WHERE ec.employer_id = u.organization_id
        """
    )
    op.execute(
        """
        UPDATE credit_transactions ct
        SET employer_id = u.id
        FROM users u
        WHERE ct.employer_id = u.organization_id
        """
    )
    op.create_foreign_key(
        "employer_credits_employer_id_fkey",
        "employer_credits",
        "users",
        ["employer_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "credit_transactions_employer_id_fkey",
        "credit_transactions",
        "users",
        ["employer_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_table("webhook_events")
    op.drop_index("ix_payments_provider_reference", table_name="payments")
    op.drop_index("ix_payments_organization_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_subscriptions_provider_subscription_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("plans")
