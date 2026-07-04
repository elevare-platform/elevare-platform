"""Enumerations for CV parsing status."""

from enum import Enum


class CVParsingStatus(str, Enum):
    """Lifecycle states for a CV parsing submission."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FLAGGED = "flagged"
