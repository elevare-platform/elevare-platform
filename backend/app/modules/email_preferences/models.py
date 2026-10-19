"""SQLAlchemy model for addresses that have turned emails off."""

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import BaseModel

# How an address was switched off.
SOURCE_EMAIL_LINK = "EMAIL_LINK"  # the Unsubscribe link (or Gmail's button) in an email
SOURCE_SETTINGS = "SETTINGS"  # the toggle in the account


class EmailSuppression(BaseModel):
    """An email address that no longer wants emails from Elevare.

    A row means "emails off"; no row means "emails on"; turning emails back on deletes
    the row. Keyed by the lower-cased address, not by user: a candidate sourced by an
    employer has no account but can still click Unsubscribe in an email.
    """

    __tablename__ = "email_suppressions"
    __table_args__ = (UniqueConstraint("email", name="uq_email_suppressions_email"),)

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
