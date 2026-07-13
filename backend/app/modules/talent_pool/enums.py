"""Enumerations for the talent pool module."""

from enum import Enum


class SourceType(str, Enum):
    """How a candidate was sourced into the talent pool."""

    EMAIL = "email"
    GMAIL_IMPORT = "gmail_import"
    REFERRAL = "referral"
    LINKEDIN = "linkedin"
    OTHER = "other"


class TalentPoolStatus(str, Enum):
    """Lifecycle state of a talent pool profile."""

    NEW = "new"
    SHORTLISTED = "shortlisted"
    PROMOTED_PENDING = (
        "promoted_pending"  # invite sent, awaiting candidate confirmation
    )
    PROMOTED = "promoted"
    ARCHIVED = "archived"
