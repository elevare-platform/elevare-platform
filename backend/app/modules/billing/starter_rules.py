"""The Starter plan's job rules (docs/08_DECISIONS.md, "Plan limits, consolidated").

* A company's FIRST published job is its taste of Professional: full AI scoring, and up to
  ``TASTE_APPLICANT_LIMIT`` applicants. The taste only works while the company is verified
  (its documents approved); until then the job is treated like any later one.
* Every later Starter job takes ``LATER_APPLICANT_LIMIT`` applicants and is not AI-scored.
* A Starter company publishes at most one new job per calendar month (Lagos time).
* A Starter job is switched off at its applicant limit or after ``STARTER_JOB_DAYS`` days,
  whichever comes first (the switching off is in ``jobs/disabling.py``).

None of this applies to Professional and above, to admins, to a job whose owner has no
company record, or while plan gating is switched off (``PLAN_GATES_ENABLED`` false, as on
production today): the functions then say "no limit".
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.billing.service import BillingService
from app.modules.employer.enums import KYCStatus
from app.modules.users.enums import UserRole
from app.modules.users.models import Organization, User

STARTER_JOB_DAYS = 30
TASTE_APPLICANT_LIMIT = 10
LATER_APPLICANT_LIMIT = 3


async def claim_taste_if_first(
    db: AsyncSession, organization_id: uuid.UUID | None, job_id: uuid.UUID
) -> None:
    """Make this job the company's taste job if the company has not had one yet.

    Called when a job is published. Whatever plan the company is on at that moment, its
    first job is its taste: a company that later falls back to Starter has already had it.
    Not committed: the caller commits it together with the publish.
    """
    if organization_id is None:
        return
    organization = await db.get(Organization, organization_id)
    if organization is not None and organization.taste_job_id is None:
        organization.taste_job_id = job_id


async def is_taste_job(
    db: AsyncSession, organization_id: uuid.UUID | None, job_id: uuid.UUID
) -> bool:
    """Whether this is the company's taste job AND the company is verified, so the taste works."""
    if organization_id is None:
        return False
    organization = await db.get(Organization, organization_id)
    return (
        organization is not None
        and organization.taste_job_id == job_id
        and organization.kyc_status == KYCStatus.APPROVED.value
    )


async def applicant_limit(db: AsyncSession, job) -> int | None:
    """How many applicants this job may take, or None when it has no limit."""
    if not settings.plan_gates_enabled:
        return None
    employer = await db.get(User, job.employer_id)
    if employer is None or employer.role == UserRole.ADMIN.value or employer.organization_id is None:
        return None
    plan = await BillingService(db).get_effective_plan(employer.organization_id)
    if plan.code != "starter":
        return None
    if await is_taste_job(db, employer.organization_id, job.id):
        return TASTE_APPLICANT_LIMIT
    return LATER_APPLICANT_LIMIT
