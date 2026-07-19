"""Add KYC fields to employer_profiles and create employer_kyc_documents table

Revision ID: e3f1a2b4c5d6
Revises: p16b_0001
Create Date: 2026-07-19 00:00:00.000000

Safety notes:
    - All new columns on employer_profiles are nullable — existing rows are unaffected.
    - employer_kyc_documents is a brand-new table — purely additive.
    - Safe to run against production with live data.
    - Grandfathers existing employers: any profile that already has
      is_profile_complete=True is backfilled to kyc_status='APPROVED' so
      live customers are not suddenly blocked from posting jobs once the
      KYC gate is enforced in application code. New/incomplete profiles
      default to 'NOT_SUBMITTED' and go through the normal KYC flow.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e3f1a2b4c5d6"
down_revision: str | None = "a90a457e7f79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -- 1. New nullable KYC columns on employer_profiles --------------------
    op.add_column(
        "employer_profiles",
        sa.Column(
            "kyc_status",
            sa.String(length=20),
            nullable=True,
            server_default="NOT_SUBMITTED",
        ),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("kyc_rejection_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("kyc_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "employer_profiles",
        sa.Column("kyc_reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # -- 2. New employer_kyc_documents table ----------------------------------
    op.create_table(
        "employer_kyc_documents",
        sa.Column("employer_profile_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["employer_profile_id"],
            ["employer_profiles.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_employer_kyc_documents_employer_profile_id"),
        "employer_kyc_documents",
        ["employer_profile_id"],
        unique=False,
    )

    # -- 3. Grandfather existing employers -----------------------------------
    op.execute(
        """
        UPDATE employer_profiles
        SET kyc_status = 'APPROVED', kyc_reviewed_at = now()
        WHERE is_profile_complete = true
        """
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_employer_kyc_documents_employer_profile_id"),
        table_name="employer_kyc_documents",
    )
    op.drop_table("employer_kyc_documents")

    op.drop_column("employer_profiles", "kyc_reviewed_at")
    op.drop_column("employer_profiles", "kyc_submitted_at")
    op.drop_column("employer_profiles", "kyc_rejection_reason")
    op.drop_column("employer_profiles", "kyc_status")
