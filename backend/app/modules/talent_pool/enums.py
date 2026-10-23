"""Enumerations for the talent pool module."""

from enum import Enum


class SourceType(str, Enum):
    """How a candidate was sourced into the talent pool."""

    EMAIL = "email"
    GMAIL_IMPORT = "gmail_import"
    ZOHO_IMPORT = "zoho_import"
    REFERRAL = "referral"
    LINKEDIN = "linkedin"
    # An email an employer typed in to send an AI interview to, with no CV and no account. It is
    # a pool row only so the interview, the interview list and the review all work as they do
    # for anyone else; it is kept out of the Talent Pool page and the matching.
    INTERVIEW_INVITE = "interview_invite"
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
