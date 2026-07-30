"""Enumerations for the candidate ingestion module"""

from datetime import timedelta
from enum import Enum

# A RUNNING/PENDING import run whose progress hasn't been touched in this
# long is treated as orphaned — e.g. the celery worker process was killed
# (OOM, the task's own hard time_limit, a container restart) mid-run, which
# bypasses the task's except-block cleanup and leaves the row stuck RUNNING
# forever. That permanently blocks new imports and incremental sync for the
# integration, since both require the current run to be finished. Set well
# above the historical import task's 2-hour hard time_limit so a genuinely
# long-running import is never mistaken for a dead one.
STALE_RUN_TIMEOUT = timedelta(hours=3)


class MailProvider(str, Enum):
    """Supported mail provider integrations."""

    GMAIL = "GMAIL"
    ZOHO = "ZOHO"
    OUTLOOK = "OUTLOOK"  # FUTURE


class ImportStatus(str, Enum):
    """Lifecycle state of a historical import run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


class IntegrationStatus(str, Enum):
    """Connection status of a mail integration"""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"
    REVOKED = "REVOKED"
