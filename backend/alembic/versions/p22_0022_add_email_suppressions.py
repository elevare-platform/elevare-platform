"""Add email_suppressions: addresses that have turned emails off

Revision ID: p22_0022
Revises: p22_0021

One row per email address that no longer wants emails from Elevare. A row means
"emails off"; no row means "emails on"; turning emails back on deletes the row.
Keyed by the lower-cased address, not by user: a candidate sourced by an employer has
no account but can still click Unsubscribe in an email.

``source`` records how it was switched off (EMAIL_LINK or SETTINGS), for support
questions like "why am I not getting emails?".

Safe on the live database: a brand-new table that nothing else references, so no
existing row or query is affected. If the new code runs for a few seconds before this
migration finishes, the send path treats a missing table as "not unsubscribed" and
logs a warning (see email_preferences/suppression.py).
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "p22_0022"
down_revision: str | None = "p22_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.UniqueConstraint("email", name="uq_email_suppressions_email"),
    )


def downgrade() -> None:
    op.drop_table("email_suppressions")
