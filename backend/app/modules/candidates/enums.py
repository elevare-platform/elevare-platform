from enum import Enum


class VisibilityStatus(str, Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"
    APPLIED_ONLY = "APPLIED_ONLY"
