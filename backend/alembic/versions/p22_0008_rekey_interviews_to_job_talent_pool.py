"""Rekey interviews to (job_id, talent_pool_profile_id), add invite token

Revision ID: p22_0008
Revises: p22_0007

Being on a job's interview list (InterviewListEntry) is what grants
access to the AI video interview, not having submitted an Application —
a candidate can be added to the interview list from Talent Pool /
Candidate Search without ever applying. This rekeys `interviews` to the
same (job_id, talent_pool_profile_id) identity InterviewListEntry uses,
makes application_id an optional best-effort link, and adds a token so
candidates with no Elevare account can start the interview from an
emailed link. No real interviews have been recorded yet (feature not
launched), so this drops and recreates the table rather than an
in-place migration.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "p22_0008"
down_revision: str | None = "p22_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("interviews")

    op.create_table(
        "interviews",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("talent_pool_profile_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("token", sa.String(length=64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column("r2_key", sa.String(length=512), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=True),
        sa.Column("ai_rationale", sa.Text(), nullable=True),
        sa.Column("ai_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(
            ["talent_pool_profile_id"], ["talent_pool_profiles.id"]
        ),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "job_id", "talent_pool_profile_id", name="uq_interviews_job_profile"
        ),
    )
    op.create_index("ix_interviews_status", "interviews", ["status"], unique=False)
    op.create_index("ix_interviews_token", "interviews", ["token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_interviews_token", table_name="interviews")
    op.drop_index("ix_interviews_status", table_name="interviews")
    op.drop_table("interviews")

    op.create_table(
        "interviews",
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="PENDING", nullable=False
        ),
        sa.Column("r2_key", sa.String(length=512), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Integer(), nullable=True),
        sa.Column("ai_rationale", sa.Text(), nullable=True),
        sa.Column("ai_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("video_expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_interviews_application_id", "interviews", ["application_id"], unique=True
    )
    op.create_index("ix_interviews_status", "interviews", ["status"], unique=False)
