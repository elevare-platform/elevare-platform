"""Enumerations for user account state and roles."""

from enum import Enum


class AccountStatus(str, Enum):
    """Possible lifecycle states for a user account."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    BANNED = "BANNED"
    DEACTIVATED = "DEACTIVATED"


class UserRole(str, Enum):
    """Role assigned to a user, controlling access to platform features."""

    ADMIN = "ADMIN"
    EMPLOYER = "EMPLOYER"
    CANDIDATE = "CANDIDATE"
