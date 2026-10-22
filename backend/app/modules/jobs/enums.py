"""Enumerations for job listings."""

from enum import Enum


class JobStatus(str, Enum):
    """Publication state of a job listing."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    # Switched off by the platform, not by the employer: the plan's applicant limit was
    # reached, the job ran its time, or the plan lapsed (see ``JobDisabledReason``). Its
    # applicants are kept, and unlike CLOSED it can be re-published once the plan allows it.
    DISABLED = "DISABLED"


class JobDisabledReason(str, Enum):
    """Why a job was switched off (``Job.disabled_reason``)."""

    APPLICANT_LIMIT = "APPLICANT_LIMIT"  # it took as many applicants as the plan allows
    EXPIRED = "EXPIRED"  # it ran for as long as the plan allows (30 days on Starter)
    PLAN_LAPSED = "PLAN_LAPSED"  # the company's plan ended and the new plan allows fewer jobs


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


class SeniorityLevel(str, Enum):
    """Seniority level for a job listing."""

    JUNIOR = "JUNIOR"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    EXECUTIVE = "EXECUTIVE"


class ModerationStatus(str, Enum):
    """Moderation state of a job listing as reviewed by an admin."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
