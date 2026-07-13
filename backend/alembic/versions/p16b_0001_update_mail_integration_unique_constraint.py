"""Update mail_integrations unique constraint to include email_address

Revision ID: p16b_0001
Revises: p16a_0002
Create Date: 2026-07-12 00:00:00.000000

Reason:
    The original constraint uq_mail_integration_user_provider enforces one
    integration per user per provider. This works for Gmail (one account per login)
    but breaks for Zoho where a single OAuth login may have multiple mail accounts
    (hr@, jobs@, careers@ etc).

    We replace it with a constraint on (user_id, provider, email_address) so
    each Zoho mailbox gets its own row while still preventing duplicates.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "p16b_0001"
down_revision: Union[str, None] = "p16a_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_mail_integration_user_provider",
        "mail_integrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_mail_integration_user_provider_email",
        "mail_integrations",
        ["user_id", "provider", "email_address"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_mail_integration_user_provider_email",
        "mail_integrations",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_mail_integration_user_provider",
        "mail_integrations",
        ["user_id", "provider"],
    )
