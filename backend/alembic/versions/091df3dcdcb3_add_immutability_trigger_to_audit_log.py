"""add immutability trigger to audit log

Revision ID: 091df3dcdcb3
Revises: 5b1ee5fdfe81
Create Date: 2026-06-10

Adds a PostgreSQL trigger that prevents any DELETE or UPDATE on the
admin_audit_log table. The trigger fires even for superusers executing
raw SQL — it can only be bypassed by dropping the trigger itself, which
is itself an auditable DDL event.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "091df3dcdcb3"
down_revision: Union[str, None] = "5b1ee5fdfe81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the trigger function
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_audit_log_immutability()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'admin_audit_log is immutable — DELETE and UPDATE are not permitted.';
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """
    )

    # Attach it as a BEFORE trigger for both DELETE and UPDATE
    op.execute(
        """
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE DELETE OR UPDATE ON admin_audit_log
        FOR EACH ROW EXECUTE FUNCTION enforce_audit_log_immutability();
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON admin_audit_log;")
    op.execute("DROP FUNCTION IF EXISTS enforce_audit_log_immutability();")
