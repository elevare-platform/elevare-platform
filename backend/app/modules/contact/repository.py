from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.contact.schemas import ContactRequest, InquiryType
from app.modules.contact.models import ContactSubmission


class ContactRepository:
    def __init__(self, session: AsyncSession):
        self._db = session
    
    async def create_contact_submission(self, payload: ContactRequest, ip_address: str | None):
        """Implementation for creating contact submission"""
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
