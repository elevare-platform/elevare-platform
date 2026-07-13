"""Data-access layer for contact form submissions."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.contact.models import ContactSubmission
from app.modules.contact.schemas import ContactRequest


class ContactRepository:
    """Handles persistence of ContactSubmission records."""

    def __init__(self, session: AsyncSession):
        """Initialise with an async database session."""
        self._db = session

    async def create_contact_submission(
        self, payload: ContactRequest, ip_address: str | None
    ):
        """Persist a contact form submission and return the created record."""
        submission = ContactSubmission(
            name=payload.name,
            email=payload.email,
            company=payload.company,
            message=payload.message,
            inquiry_type=payload.inquiry_type.value,
            ip_address=ip_address,
        )
        self._db.add(submission)
        await self._db.commit()
        return submission
