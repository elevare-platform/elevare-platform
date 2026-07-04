"""Enumerations for candidate profile visibility."""
from enum import Enum


class VisibilityStatus(str, Enum):
    """Controls who can view a candidate's profile."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    APPLIED_ONLY = "APPLIED_ONLY"
