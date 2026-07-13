"""Enumerations for job application status."""

from enum import Enum


class ApplicationStatus(str, Enum):
    """Lifecycle states for a job application."""

    SUBMITTED = "SUBMITTED"
    REVIEWING = "REVIEWING"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    HIRED = "HIRED"
    WITHDRAWN = "WITHDRAWN"
