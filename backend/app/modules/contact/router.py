"""Public contact form endpoint."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.email import EmailService, get_email_service
from app.modules.contact.schemas import ContactRequest, ContactResponse
from app.modules.contact.service import ContactService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ContactResponse, status_code=200)
async def contact(
    payload: ContactRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
) -> ContactResponse:
    """Accept a contact form submission.

    Honeypot check happens first — if populated, we return 200 silently
    without touching the database or sending any email.
    """
    if payload.honeypot:
        # Silent rejection — bot filled the hidden field
        return ContactResponse(message="Thank you, we'll be in touch within 24 hours.")

    ip_address = request.client.host if request.client else None

    service = ContactService(db, email_service)

    await service.process_contact_submission(
        payload=payload,
        ip_address=ip_address,
    )

    return ContactResponse(message="Thank you, we'll be in touch within 24 hours.")
