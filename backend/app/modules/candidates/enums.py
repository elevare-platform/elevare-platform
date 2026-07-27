"""Enumerations for candidate profile visibility and search."""

from enum import Enum


class VisibilityStatus(str, Enum):
    """Controls who can view a candidate's profile."""

    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    APPLIED_ONLY = "APPLIED_ONLY"


class AvailabilityBucket(str, Enum):
    """Coarse availability filter derived from ``notice_period_days``.

    There is no dedicated availability column on ``CandidateProfile`` — this
    bucketing is applied at query time against ``notice_period_days`` so no
    migration is required.
    """

    IMMEDIATE = "IMMEDIATE"  # notice_period_days <= 7
    TWO_WEEKS = "TWO_WEEKS"  # notice_period_days <= 14
    ONE_MONTH = "ONE_MONTH"  # notice_period_days <= 30
    FLEXIBLE = "FLEXIBLE"  # no constraint (includes unknown/null notice)
