"""Who may have their AI interviews scored.

An interview is scored when the job's owner is Elevare itself, when the interview
was paid for with credits, or when the organization is on the Professional plan or
above. One rule, used by the background task that scores a finished interview and
by the "score this interview" request, so the two can never disagree.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.service import BillingService
from app.modules.credits.service import CreditsService
from app.modules.jobs.models import Job
from app.modules.users.enums import UserRole


async def assert_can_score_interviews(
    db: AsyncSession, job: Job, interview_id: uuid.UUID | None = None
) -> None:
    """Raise PlanUpgradeRequiredException unless this interview may be AI-scored.

    Elevare's own admin accounts are exempt. They are the platform, not a paying
    customer, and have no organization, so a plan lookup would always read as
    "Starter" and silently stop their interviews from ever being scored. The
    talent pool makes the same exemption (``_can_auto_score``) and job posting
    skips the quota check for an owner with no organization.

    An interview the customer paid credits for is scored on any plan: charging
    for an interview and then leaving it unscored for want of a plan would be
    paying twice for one thing. A refunded interview no longer counts as paid.
    Pass ``interview_id`` to apply that rule.

    ``job.employer`` must be loaded; ``InterviewRepository`` loads it.
    """
    employer = job.employer
    if employer is not None and employer.role == UserRole.ADMIN.value:
        return
    if (
        interview_id is not None
        and employer is not None
        and employer.organization_id is not None
        and await CreditsService(db).has_outstanding_interview_charge(
            employer.organization_id, interview_id
        )
    ):
        return
    await BillingService(db).assert_professional_or_above(employer.organization_id)
