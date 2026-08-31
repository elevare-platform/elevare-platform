"""Organization refactor — employer_profiles becomes organizations, multi-seat membership

Revision ID: p21_0001
Revises: 34a46ce1dbe3
Create Date: 2026-08-07 00:00:00.000000

Part of the subscription/payment work (see
docs/subscription-payment-architecture-review.md, Phase 1a). Billing needs
a company-level entity that can be shared by more than one login —
`employer_profiles` was a strict 1:1 with `users`, so it's repurposed into
`organizations` here rather than adding a parallel table.

Safety notes:
    - There is exactly one real employer account in production today (plus
      whatever pilot/test rows exist). This migration is written to be
      correct for zero, one, or many existing `employer_profiles` rows —
      the backfill is a plain UPDATE ... FROM join, not a row-count
      assumption.
    - Every existing `employer_profiles` row's owning user becomes that
      organization's OWNER, preserving current access exactly — no
      employer loses anything they could do before this migration.
    - All new `users` columns are nullable; existing CANDIDATE/ADMIN rows
      are untouched.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p21_0001"
down_revision: str | None = "34a46ce1dbe3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- 1. employer_profiles -> organizations --------------------------------
    op.rename_table("employer_profiles", "organizations")

    # -- 2. New membership columns on users ------------------------------------
    op.add_column("users", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.add_column(
        "users", sa.Column("organization_role", sa.String(length=20), nullable=True)
    )
    op.add_column("users", sa.Column("invited_by_id", sa.UUID(), nullable=True))
    op.add_column(
        "users",
        sa.Column("joined_organization_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_users_organization_id"), "users", ["organization_id"], unique=False
    )
    op.create_foreign_key(
        "fk_users_organization_id_organizations",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_users_invited_by_id_users",
        "users",
        "users",
        ["invited_by_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -- 3. created_by on organizations (replaces the old owner FK) -----------
    op.add_column("organizations", sa.Column("created_by", sa.UUID(), nullable=True))

    # -- 4. Backfill: every existing profile's owner becomes that org's OWNER -
    # Correct regardless of row count — 0 rows is a no-op, N rows all backfill
    # in one statement.
    op.execute(
        """
        UPDATE organizations o
        SET created_by = o.user_id
        """
    )
    op.execute(
        """
        UPDATE users u
        SET organization_id = o.id,
            organization_role = 'OWNER',
            joined_organization_at = o.created_at
        FROM organizations o
        WHERE o.user_id = u.id
        """
    )
    op.create_foreign_key(
        "fk_organizations_created_by_users",
        "organizations",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )

    # -- 5. Drop the old 1:1 owner FK — organizations.user_id ------------------
    op.drop_index("ix_employer_profiles_user_id", table_name="organizations")
    op.drop_constraint(
        "employer_profiles_user_id_fkey", "organizations", type_="foreignkey"
    )
    op.drop_column("organizations", "user_id")

    # -- 6. employer_kyc_documents.employer_profile_id -> organization_id -----
    op.alter_column(
        "employer_kyc_documents", "employer_profile_id", new_column_name="organization_id"
    )
    op.execute(
        "ALTER INDEX ix_employer_kyc_documents_employer_profile_id "
        "RENAME TO ix_employer_kyc_documents_organization_id"
    )

    # -- 7. invite_tokens gains organization_id (teammate vs new-account invite)
    op.add_column(
        "invite_tokens", sa.Column("organization_id", sa.UUID(), nullable=True)
    )
    op.create_foreign_key(
        "fk_invite_tokens_organization_id_organizations",
        "invite_tokens",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_invite_tokens_organization_id_organizations",
        "invite_tokens",
        type_="foreignkey",
    )
    op.drop_column("invite_tokens", "organization_id")

    op.execute(
        "ALTER INDEX ix_employer_kyc_documents_organization_id "
        "RENAME TO ix_employer_kyc_documents_employer_profile_id"
    )
    op.alter_column(
        "employer_kyc_documents", "organization_id", new_column_name="employer_profile_id"
    )

    op.add_column(
        "organizations", sa.Column("user_id", sa.UUID(), nullable=True)
    )
    op.execute(
        """
        UPDATE organizations o
        SET user_id = o.created_by
        """
    )
    op.alter_column("organizations", "user_id", nullable=False)
    op.create_index(
        "ix_employer_profiles_user_id", "organizations", ["user_id"], unique=True
    )
    op.create_foreign_key(
        "employer_profiles_user_id_fkey",
        "organizations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "fk_organizations_created_by_users", "organizations", type_="foreignkey"
    )
    op.drop_column("organizations", "created_by")

    op.drop_constraint("fk_users_invited_by_id_users", "users", type_="foreignkey")
    op.drop_constraint(
        "fk_users_organization_id_organizations", "users", type_="foreignkey"
    )
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_column("users", "joined_organization_at")
    op.drop_column("users", "invited_by_id")
    op.drop_column("users", "organization_role")
    op.drop_column("users", "organization_id")

    op.rename_table("organizations", "employer_profiles")
