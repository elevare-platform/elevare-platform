"""Celery tasks for employer KYC email notifications."""

import asyncio
import logging

from app.core.celery_app import celery
from app.core.email import get_email_service

logger = logging.getLogger(__name__)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_kyc_submission_notification_email(
    self,
    admin_email: str,
    company_name: str | None,
    organization_id: str,
) -> None:
    """Notify an admin that an employer submitted KYC documents for review."""

    async def _send():
        service = get_email_service()
        await service.send_kyc_submission_notification(
            admin_email=admin_email,
            company_name=company_name,
            organization_id=organization_id,
        )

    try:
        asyncio.run(_send())
        logger.info("KYC submission notification email sent to %s", admin_email)
    except Exception as exc:
        logger.error(
            "Failed to send KYC submission notification email to %s: %s",
            admin_email,
            exc,
        )
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_kyc_approved_email(
    self,
    employer_email: str,
    company_name: str | None,
) -> None:
    """Notify an employer that their KYC submission was approved."""

    async def _send():
        service = get_email_service()
        await service.send_kyc_approved(
            employer_email=employer_email,
            company_name=company_name,
        )

    try:
        asyncio.run(_send())
        logger.info("KYC approved email sent to %s", employer_email)
    except Exception as exc:
        logger.error("Failed to send KYC approved email to %s: %s", employer_email, exc)
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_kyc_rejection_email(
    self,
    employer_email: str,
    company_name: str | None,
    reason: str | None,
) -> None:
    """Notify an employer that their KYC submission was rejected."""

    async def _send():
        service = get_email_service()
        await service.send_kyc_rejection(
            employer_email=employer_email,
            company_name=company_name,
            reason=reason,
        )

    try:
        asyncio.run(_send())
        logger.info("KYC rejection email sent to %s", employer_email)
    except Exception as exc:
        logger.error("Failed to send KYC rejection email to %s: %s", employer_email, exc)
        raise self.retry(exc=exc) from exc
