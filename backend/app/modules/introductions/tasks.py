"""Celery tasks for introduction request email notifications."""

import asyncio
import logging

from app.core.celery_app import celery
from app.core.email import get_email_service

logger = logging.getLogger(__name__)


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_introduction_request_email(
    self,
    candidate_email: str,
    accept_url: str,
    decline_url: str,
    job_title: str,
) -> None:
    """Send an introduction request email with accept/decline magic links."""

    async def _send():
        service = get_email_service()
        await service.send_introduction_request(
            candidate_email=candidate_email,
            accept_url=accept_url,
            decline_url=decline_url,
            job_title=job_title,
        )

    try:
        asyncio.run(_send())
        logger.info(
            "Introduction request email sent to %s for role '%s'",
            candidate_email,
            job_title,
        )
    except Exception as exc:
        logger.error(
            "Failed to send introduction request email to %s: %s", candidate_email, exc
        )
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_introduction_accepted_email(
    self,
    employer_email: str,
    job_title: str,
    profile_url: str,
) -> None:
    """Notify employer that a candidate accepted their introduction request."""

    async def _send():
        service = get_email_service()
        await service.send_introduction_accepted(
            employer_email=employer_email,
            job_title=job_title,
            profile_url=profile_url,
        )

    try:
        asyncio.run(_send())
        logger.info("Introduction accepted email sent to %s", employer_email)
    except Exception as exc:
        logger.error(
            "Failed to send introduction accepted email to %s: %s", employer_email, exc
        )
        raise self.retry(exc=exc) from exc


@celery.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def send_introduction_declined_email(
    self,
    employer_email: str,
    job_title: str,
) -> None:
    """Notify employer that a candidate declined their introduction request."""

    async def _send():
        service = get_email_service()
        await service.send_introduction_declined(
            employer_email=employer_email,
            job_title=job_title,
        )

    try:
        asyncio.run(_send())
        logger.info("Introduction declined email sent to %s", employer_email)
    except Exception as exc:
        logger.error(
            "Failed to send introduction declined email to %s: %s", employer_email, exc
        )
        raise self.retry(exc=exc) from exc
