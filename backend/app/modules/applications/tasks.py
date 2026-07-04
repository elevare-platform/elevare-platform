"""Asynchronous Celery tasks for sending email notifications.

Uses centralized email utilities to send formatted emails for
verification, password resets, and other system alerts.
Also creates in-app Notification records for user-facing events.
"""

import logging

from app.core.celery_app import celery
from app.core.email import get_email_service

logger = logging.getLogger(__name__)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_application_confirmation(self, candidate_email, job_title, company_name):
    """Send an application confirmation email to the candidate."""
    import asyncio

    async def _send():
        service = get_email_service()
        await service.send_application_confirmation(candidate_email, job_title, company_name)

    try:
        asyncio.run(_send())
    except Exception as exc:
        logger.error(f"Failed to send application confirmation to {candidate_email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_status_update(self, candidate_email, job_title, new_status):
    """Send an application status update email to the candidate."""
    import asyncio

    async def _send():
        service = get_email_service()
        await service.send_status_update(candidate_email, job_title, new_status)

    try:
        asyncio.run(_send())
        logger.info(f"Status update email sent to {candidate_email}")
    except Exception as exc:
        logger.error(f"Failed to send status update to {candidate_email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_employer_notification(self, employer_email, job_title, candidate_name):
    """Send a new-application notification email to the employer."""
    import asyncio

    async def _send():
        service = get_email_service()
        await service.send_employer_notification(employer_email, job_title, candidate_name)

    try:
        asyncio.run(_send())
        logger.info(f"Employer notification email sent to {employer_email}")
    except Exception as exc:
        logger.error(f"Failed to send employer notification to {employer_email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_verification_email(self, token: str, email: str, next_url: str | None = None) -> None:
    """Send account verification email with retry logic."""
    import asyncio

    async def _send():
        service = get_email_service()
        await service.send_verification_email(email, token, next_url=next_url)

    try:
        asyncio.run(_send())
        logger.info(f"Verification email sent to {email}")
    except Exception as exc:
        logger.error(f"Failed to send verification email to {email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_job_moderation_email(
    self,
    employer_email: str,
    job_id: str,
    job_title: str,
    action: str,
    reason: str | None = None,
) -> None:
    """Notify employer of job approval or rejection via email."""
    import asyncio

    async def _send():
        service = get_email_service()
        await service.send_job_moderation_status(
            employer_email,
            {"id": job_id, "title": job_title},
            action,
            reason,
        )

    try:
        asyncio.run(_send())
        logger.info("Job moderation email sent to %s (action=%s)", employer_email, action)
    except Exception as exc:
        logger.error("Failed to send job moderation email to %s: %s", employer_email, exc)
        raise self.retry(exc=exc) from exc
