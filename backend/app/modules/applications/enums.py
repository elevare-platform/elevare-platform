from enum import Enum


class ApplicationStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    REVIEWING = "REVIEWING"
    SHORTLISTED = "SHORTLISTED"
    REJECTED = "REJECTED"
    HIRED = "HIRED"
    WITHDRAWN = "WITHDRAWN"
