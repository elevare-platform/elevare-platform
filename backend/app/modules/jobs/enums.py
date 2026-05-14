from enum import Enum


class JobStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class WorkModel(str, Enum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"


class ContractType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    FREELANCE = "FREELANCE"
    INTERNSHIP = "INTERNSHIP"
    CONTRACT = "CONTRACT"

