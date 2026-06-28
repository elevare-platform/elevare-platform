from enum import Enum

class SourceType(str, Enum):
    EMAIL = "email"
    REFERRAL = "referral"
    LINKEDIN = "linkedin"
    OTHER = "other"


class TalentPoolStatus(str, Enum):
    NEW = "new"
    SHORTLISTED = "shortlisted"
    PROMOTED_PENDING = "promoted_pending"  # invite sent, awaiting candidate confirmation
    PROMOTED = "promoted"
    ARCHIVED = "archived"
