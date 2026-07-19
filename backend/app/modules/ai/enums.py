"""Enumerations for CV parsing status."""

from enum import Enum


class CVParsingStatus(str, Enum):
    """Lifecycle states for a CV parsing submission."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    FLAGGED = "flagged"


class JobDescriptionMode(str, Enum):
    """Modes for the AI job description writer."""

    GENERATE = "GENERATE"
    IMPROVE = "IMPROVE"
    SHORTEN = "SHORTEN"
    EXPAND = "EXPAND"
    REWRITE_PROFESSIONAL = "REWRITE_PROFESSIONAL"
    MORE_INCLUSIVE = "MORE_INCLUSIVE"
    IMPROVE_CLARITY = "IMPROVE_CLARITY"


class JobDescriptionField(str, Enum):
    """Which job description field the AI is targeting."""

    ABOUT_THE_ROLE = "about_the_role"
    KEY_RESPONSIBILITIES = "key_responsibilities"
    REQUIREMENTS = "requirements"
