"""Asynchronous Celery tasks for sending email notifications.

Uses centralized email utilities to send formatted emails for
verification, password resets, and other system alerts.
Also creates in-app Notification records for user-facing events.
"""

import logging

from app.core.celery_app import celery_app
from app.core.email import get_email_service

logger = logging.getLogger(__name__)

email_service = get_email_service()


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
async def send_application_confirmation(self, candidate_email, job_title, company_name):
    """Send an application confirmation email to the candidate."""
    try:
        await email_service.send_employer_notification(
            candidate_email,
            job_title,
            company_name,
        )
    except Exception as exc:
        logger.error(f"Failed to send application confirmation to {candidate_email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
async def send_status_update(self, candidate_email, job_title, new_status):
    """Send an application status update email to the candidate."""
    try:
        await email_service.send_status_update(
            candidate_email,
            job_title,
            new_status,
        )
        logger.info(f"Status update email sent to {candidate_email}")
    except Exception as exc:
        logger.error(f"Failed to send status update to {candidate_email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
async def send_employer_notification(self, employer_email, job_title, candidate_name):
    """Send a new-application notification email to the employer."""
    try:
        await email_service.send_employer_notification(
            employer_email,
            job_title,
            candidate_name,
        )
        logger.info(f"Employer notification email sent to {employer_email}")
    except Exception as exc:
        logger.error(f"Failed to send employer notification to {employer_email}: {exc}")
        raise self.retry(exc=exc) from exc


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
async def send_verification_email(self, token: str, email: str) -> None:
    """Send account verification email with retry logic."""
    try:
        await email_service.send_verification_email(
            email,
            token,
        )
        logger.info(f"Verification email sent to {email}")
    except Exception as exc:
        logger.error(f"Failed to send verification email to {email}: {exc}")
        raise self.retry(exc=exc) from exc
