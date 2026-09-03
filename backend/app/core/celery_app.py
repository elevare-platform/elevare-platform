"""Celery application configuration for the auction platform.

This module initializes the Celery app instance and configures it with
Redis as both the message broker and result backend. It also sets
default task execution policies (timeouts, serialization, etc.).
"""

import logging

import sentry_sdk
from celery import Celery
from sentry_sdk.integrations.celery import CeleryIntegration

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialise Sentry for Celery workers
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        release=settings.app_version,
        integrations=[CeleryIntegration()],
        traces_sample_rate=0.2,
    )


def _redis_url_with_ssl(url: str) -> str:
    """Append ssl_cert_reqs=CERT_NONE for rediss:// URLs (required by Celery)."""
    if url.startswith("rediss://") and "ssl_cert_reqs" not in url:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}ssl_cert_reqs=CERT_NONE"
    return url


_broker_url = _redis_url_with_ssl(settings.redis_url)
_backend_url = _redis_url_with_ssl(settings.redis_url)

celery = Celery(
    "Elevare",
    broker=_broker_url,
    backend=_backend_url,
    include=[
        "core.tasks",  # health check task
        "app.modules.ai.tasks",  # CV parsing pipeline
        "app.modules.applications.tasks",
        "app.modules.billing.tasks",  # payment reconciliation
        "app.modules.contact.tasks",  # contact form notification emails
        "app.modules.employer.tasks",  # KYC submission notification emails
        "app.modules.ingestion.tasks",  # candidate ingestion
        "app.modules.introductions.tasks",  # introduction request emails
        "app.modules.interviews.tasks",  # AI video interview invite emails
        "app.modules.users.tasks",  # role-switch self-heal backstop
    ],
)

# Celery configuration
celery.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Result backend
    result_expires=3600,
    # Task execution
    task_always_eager=False,  # Always run tasks in the worker, never inline
    task_track_started=True,
    task_time_limit=300,  # Hard kill after 5 minutes
    task_soft_time_limit=240,  # Warn after 4 minutes
    # Worker
    worker_prefetch_multiplier=1,
    # Recycle a forked child after 100 tasks (was 1000) — a fresh process
    # sheds any accumulated memory, including from leaks we haven't found
    # yet, before it can build up enough to get OOM-killed. See
    # docker-compose.prod.yml's celery_worker service for the 2G ceiling
    # this is meant to stay well under.
    worker_max_tasks_per_child=100,
    # Route mail ingestion work to its own queue, consumed by a separate
    # worker (see docker-compose.prod.yml's celery_worker_ingestion). Import
    # tasks are long-running (now checkpointed, but still minutes-to-hours
    # per execution) and I/O-bound, not memory/CPU-heavy like CV parsing/
    # OCR/embeddings — without this, one employer's import occupies a
    # worker slot shared with everyone else's CV parsing, scoring, and
    # notification emails for the duration of the run. At 50 employers,
    # even a couple of concurrent imports would stall unrelated work
    # system-wide. Keeping them on a separate queue/worker means a burst of
    # imports can never block anything outside mail ingestion itself.
    task_routes={
        "app.modules.ingestion.tasks.run_historical_import_task": {
            "queue": "ingestion"
        },
        "app.modules.ingestion.tasks.sync_all_mailboxes_task": {"queue": "ingestion"},
    },
    # Beat schedule — nightly off-peak jobs
    beat_schedule={
        "recompute-stale-scores-nightly": {
            "task": "app.modules.ai.tasks.recompute_stale_scores_task",
            "schedule": 60 * 60 * 24,  # every 24 hours
            "options": {"expires": 60 * 60},
        },
        "backfill-missing-candidate-embeddings": {
            "task": "app.modules.ai.tasks.backfill_missing_candidate_embeddings_task",
            "schedule": 60 * 60,  # every hour — backstop, not the primary trigger
            "options": {"expires": 60 * 55},
        },
        "sync-all-mailboxes": {
            "task": "app.modules.ingestion.tasks.sync_all_mailboxes_task",
            "schedule": 60 * 15,  # every 15 minutes
            "options": {"expires": 60 * 14},  # discard if not picked up before next run
        },
        "reap-stale-import-runs": {
            "task": "app.modules.ingestion.tasks.reap_stale_import_runs_task",
            "schedule": 60 * 30,  # every 30 minutes
            "options": {"expires": 60 * 29},
        },
        "reconcile-pending-payments": {
            "task": "app.modules.billing.tasks.reconcile_pending_payments_task",
            "schedule": 60 * 15,  # every 15 minutes
            "options": {"expires": 60 * 14},
        },
        "expire-lapsed-subscriptions": {
            "task": "app.modules.billing.tasks.expire_lapsed_subscriptions_task",
            "schedule": 60 * 60,  # every hour
            "options": {"expires": 60 * 55},
        },
        "expire-interview-videos": {
            "task": "app.modules.interviews.tasks.expire_interview_videos_task",
            "schedule": 60 * 60 * 6,  # every 6 hours
            "options": {"expires": 60 * 60 * 5},
        },
        "reap-stale-interviews": {
            "task": "app.modules.interviews.tasks.reap_stale_interviews_task",
            "schedule": 60 * 30,  # every 30 minutes
            "options": {"expires": 60 * 29},
        },
        "heal-role-switch-profiles": {
            "task": "app.modules.users.tasks.heal_role_switch_profiles_task",
            # Backstop, not a primary trigger. Should almost never find
            # anything (see the task's docstring). Running it every 6 hours
            # balances catching a user-facing 500 reasonably quickly against
            # a sweep that's expected to no-op almost every time it fires.
            "schedule": 60 * 60 * 6,
            "options": {"expires": 60 * 60 * 5},
        },
    },
)
