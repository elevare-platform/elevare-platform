from enum import Enum


class AccountStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    BANNED = "BANNED"


class UserRole(str, Enum):
    USER = "USER"
    ADMIN = "ADMIN"
    GUEST = "GUEST"
    EMPLOYER = "EMPLOYER"
