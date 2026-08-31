from enum import Enum


class KYCStatus(str, Enum):
    NOT_SUBMITTED = "NOT_SUBMITTED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OrganizationRole(str, Enum):
    """A member's role within their Organization — separate from `UserRole`.

    `UserRole` (users/enums.py) is platform-wide (EMPLOYER/CANDIDATE/ADMIN).
    This is company-scoped: who can manage this specific organization's
    billing and team, independent of the platform role.
    """

    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
