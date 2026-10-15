"""Who may have their AI interviews scored.

AI scoring of interviews is a Professional-plan feature. One rule, used by the
background task that scores a finished interview and by the "score this
interview" request, so the two can never disagree.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.service import BillingService
from app.modules.jobs.models import Job
from app.modules.users.enums import UserRole


async def assert_can_score_interviews(db: AsyncSession, job: Job) -> None:
    """Raise PlanUpgradeRequiredException unless the job's owner may have
    interviews AI-scored.

    Elevare's own admin accounts are exempt. They are the platform, not a paying
    customer, and have no organization, so a plan lookup would always read as
    "Starter" and silently stop their interviews from ever being scored. The
    talent pool makes the same exemption (``_can_auto_score``) and job posting
    skips the quota check for an owner with no organization.

    ``job.employer`` must be loaded; ``InterviewRepository`` loads it.
    """
    employer = job.employer
    if employer is not None and employer.role == UserRole.ADMIN.value:
        return
    await BillingService(db).assert_professional_or_above(employer.organization_id)
