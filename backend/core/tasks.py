"""Core platform Celery tasks.

Contains infrastructure-level tasks that are not tied to a specific
business domain — currently just the worker health check.
"""

import logging

from config.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="core.tasks.health_check")
def health_check() -> str:
    """Celery worker health check — runs every 5 minutes via Beat.

    Returns a simple "ok" string. If this task stops appearing in the
    Celery result backend, the worker is down or Beat has stopped
    scheduling tasks.

    To verify manually:
        celery -A config.celery_app.celery inspect active
        celery -A config.celery_app.celery call apps.core.tasks.health_check

    Returns:
        "ok" on success.

    """
    logger.info("Celery health check: ok")
    return "ok"
