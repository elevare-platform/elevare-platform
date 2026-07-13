"""Enumerations for the candidate ingestion module"""

from enum import Enum


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
