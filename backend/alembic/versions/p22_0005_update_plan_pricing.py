"""Update plan pricing — Starter drops to 1 free job posting, Professional priced at NGN 45,000/month

Revision ID: p22_0005
Revises: p22_0004

Placeholder pricing pending a real number from product/HR — see
docs/subscription-payment-architecture-review.md. Recorded as an explicit
migration (not a silent seed-data edit) so the change is reviewable and
reversible, same as every other pricing/plan change in this project.
"""

from alembic import op

revision: str = "p22_0005"
down_revision: str | None = "p22_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE plans SET job_posting_limit = 1 WHERE code = 'starter'")
    op.execute("UPDATE plans SET price_kobo = 4500000 WHERE code = 'professional'")


def downgrade() -> None:
    op.execute("UPDATE plans SET job_posting_limit = 3 WHERE code = 'starter'")
    op.execute("UPDATE plans SET price_kobo = 0 WHERE code = 'professional'")
