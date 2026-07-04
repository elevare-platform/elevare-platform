"""Celery tasks for contact form email notifications."""

import asyncio
import logging

from app.core.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_contact_notification_task(
    self,
    recipient: str,
    name: str,
    sender_email: str,
    company: str | None,
    message: str,
    inquiry_type: str,
) -> None:
    """Celery task — send contact form notification email."""
    asyncio.run(
        _send_contact_notification_async(
            recipient=recipient,
            name=name,
            sender_email=sender_email,
            company=company,
            message=message,
            inquiry_type=inquiry_type,
        )
    )


async def _send_contact_notification_async(
    recipient: str,
    name: str,
    sender_email: str,
    company: str | None,
    message: str,
    inquiry_type: str,
) -> None:
    """Send contact notification email asynchronously."""
    from app.core.email import get_email_service

    email_service = get_email_service()

    try:
        await email_service.send_contact_notification(
            recipient=recipient,
            name=name,
            sender_email=sender_email,
            company=company,
            message=message,
            inquiry_type=inquiry_type,
        )
        logger.info(
            "Contact notification sent — type=%s recipient=%s from=%s",
            inquiry_type,
            recipient,
            sender_email,
        )
    except Exception:
        logger.exception("Failed to send contact notification email")
        raise
