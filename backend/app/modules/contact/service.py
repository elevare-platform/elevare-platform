"""Business logic for processing contact form submissions."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.email import EmailService

from .repository import ContactRepository
from .schemas import ContactRequest, InquiryType

logger = logging.getLogger(__name__)


class ContactService:
    """Service for handling contact form submissions."""

    def __init__(self, db: AsyncSession, email_service: EmailService):
        """Initialize the service with database session and email service."""
        self.db = db
        self.email_service = email_service
        self._contact_repo = ContactRepository(db)

    async def process_contact_submission(
        self,
        payload: ContactRequest,
        ip_address: str | None,
    ) -> None:
        """Persist the submission and send the appropriate notification email."""

        submission = await self._contact_repo.create_contact_submission(payload, ip_address)

        # Route email to the correct recipient
        recipient = (
            settings.sales_email
            if payload.inquiry_type == InquiryType.employer_inquiry
            else settings.contact_email
        )

        await self.email_service.send_contact_notification(
            recipient=recipient,
            name=payload.name,
            sender_email=payload.email,
            company=payload.company,
            message=payload.message,
            inquiry_type=payload.inquiry_type.value,
        )

        logger.info(
            "Contact submission processed — type=%s ip=%s",
            payload.inquiry_type.value,
            ip_address,
        )
