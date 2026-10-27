"""Add the tables that remember which CVs have been looked at

Revision ID: p22_0032
Revises: p22_0031

Five brand-new tables (docs/08_DECISIONS.md, item 35): the moment an employer first used the
"new" markers, which talent pool CVs and which applicants an employer has opened, and for each
shared link when it was last visited and which candidates its reader opened. Nothing in an existing table changes, so
the old code never notices them and the new code needs only the tables, which exist from the
moment this runs. Safe on the live database: empty tables with foreign keys and two small unique
indexes.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0032"
down_revision: str | None = "p22_0031"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def _uuid(name: str, target: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name, postgresql.UUID(as_uuid=True), sa.ForeignKey(target, ondelete="CASCADE"), nullable=nullable
    )


def upgrade() -> None:
    op.create_table(
        "employer_seen_baselines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        _uuid("employer_id", "users.id"),
        sa.Column("baseline_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("employer_id", name="uq_employer_seen_baselines_employer"),
    )
    op.create_table(
        "talent_pool_profile_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        _uuid("employer_id", "users.id"),
        _uuid("talent_pool_profile_id", "talent_pool_profiles.id"),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("employer_id", "talent_pool_profile_id", name="uq_talent_pool_profile_view"),
    )
    op.create_table(
        "application_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        _uuid("employer_id", "users.id"),
        _uuid("application_id", "applications.id"),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("employer_id", "application_id", name="uq_application_view"),
    )
    op.create_table(
        "job_access_token_visits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        _uuid("token_id", "job_access_tokens.id"),
        sa.Column("previous_visit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_visit_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_id", name="uq_job_access_token_visits_token"),
    )
    op.create_table(
        "job_access_token_item_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        *_timestamps(),
        _uuid("token_id", "job_access_tokens.id"),
        sa.Column("item_key", sa.String(16), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_id", "item_key", name="uq_shared_link_item_view"),
    )


def downgrade() -> None:
    op.drop_table("job_access_token_item_views")
    op.drop_table("job_access_token_visits")
    op.drop_table("application_views")
    op.drop_table("talent_pool_profile_views")
    op.drop_table("employer_seen_baselines")
