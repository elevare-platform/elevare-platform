"""Enumerations for job listings."""

from enum import Enum


class JobStatus(str, Enum):
    """Publication state of a job listing."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"


class WorkModel(str, Enum):
    """Where the work is performed."""

    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"


class ContractType(str, Enum):
    """Employment contract type for a job listing."""

    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    FREELANCE = "FREELANCE"
    INTERNSHIP = "INTERNSHIP"
    CONTRACT = "CONTRACT"


class WorkLocation(str, Enum):
    """Geographic scope of the job — local or international candidates."""

    LOCAL = "LOCAL"
    INTERNATIONAL = "INTERNATIONAL"

