"""Monthly allowances: how many CV uploads and AI scores a company has used this month, and
whether it may use one more.

The limits live on the plan (``Plan.monthly_cv_uploads`` and ``Plan.monthly_ai_scores``).
The usage is NOT a counter that could drift: it is counted from rows the platform already
writes (every upload is a ``parsed_cv_submissions`` row, every AI scoring call a
``fit_scoring_costs`` row), over the calendar month in Lagos time. Nothing has to be reset
on the 1st.

While plan gating is switched off (``PLAN_GATES_ENABLED`` false, as on production today)
every company resolves to Professional. The allowances then do NOT apply, like every other
gate, otherwise deploying this code would cap live companies before gating is switched on.

A check and the work it guards are not one atomic step, so two requests at the same moment
can overshoot a limit by a little. That is accepted: the limits are about cost, not about a
hard guarantee.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PlanLimitReachedException
from app.modules.ai.models import FitScoringCost, ParsedCVSubmission
from app.modules.billing.service import BillingService
from app.modules.billing.starter_rules import is_taste_job
from app.modules.jobs.models import Job
from app.modules.users.models import User

# Nigeria has one time zone and no daylight saving, so "the 1st" is the same for everyone.
LAGOS = ZoneInfo("Africa/Lagos")


def month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The calendar month in Lagos time that contains ``now``, as (start, next_start) in UTC.

    The month starts at midnight on the 1st in Lagos, which is 23:00 UTC the evening before.
    """
    local = (now or datetime.now(UTC)).astimezone(LAGOS)
    start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # 32 days after the 1st is always in the next month; snap it back to that month's 1st.
    next_start = (start + timedelta(days=32)).replace(day=1)
    return start.astimezone(UTC), next_start.astimezone(UTC)


@dataclass(frozen=True)
class Allowance:
    """One monthly allowance of one company: what the plan gives, and what is used."""

    name: str  # for messages, for example "CV uploads"
    limit: int | None  # None = unlimited, 0 = none
    used: int
    resets_at: datetime

    @property
    def unlimited(self) -> bool:
        return self.limit is None

    @property
    def remaining(self) -> int | None:
        """How many are left this month, or None when there is no limit."""
        if self.limit is None:
            return None
        return max(0, self.limit - self.used)

    @property
    def exhausted(self) -> bool:
        return self.limit is not None and self.used >= self.limit

    def message(self) -> str:
        """A sentence the user can read as it is."""
        reset = self.resets_at.astimezone(LAGOS).strftime("%-d %B")
        return (
            f"Your plan includes {self.limit} {self.name} a month and you have used "
            f"{self.used}. It resets on {reset}. Upgrade your plan to continue."
        )


class AllowanceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _limits(self, organization_id: uuid.UUID | None) -> tuple[int | None, int | None]:
        """(uploads, scores) allowed per month. (None, None) = no limits apply."""
        if organization_id is None or not settings.plan_gates_enabled:
            return None, None
        plan = await BillingService(self._db).get_effective_plan(organization_id)
        return plan.monthly_cv_uploads, plan.monthly_ai_scores

    async def _count_uploads(self, organization_id: uuid.UUID, start: datetime) -> int:
        """CV uploads this month by anyone in the company. A failed read still cost money,
        so every row counts."""
        stmt = (
            select(func.count(ParsedCVSubmission.id))
            .join(User, User.id == ParsedCVSubmission.uploaded_by)
            .where(
                User.organization_id == organization_id,
                ParsedCVSubmission.created_at >= start,
            )
        )
        return (await self._db.execute(stmt)).scalar_one()

    async def _count_scores(self, organization_id: uuid.UUID, start: datetime) -> int:
        """AI scores this month for the company's jobs, one per candidate and job.

        One scoring can take several calls (a retry, or a second try on a stronger model),
        each written as its own cost row, so rows are counted once per candidate and job.
        """
        candidate = func.coalesce(
            cast(FitScoringCost.application_id, String),
            cast(FitScoringCost.talent_pool_profile_id, String),
        )
        stmt = (
            select(func.count(distinct(func.concat(candidate, ":", cast(FitScoringCost.job_id, String)))))
            .join(Job, Job.id == FitScoringCost.job_id)
            .join(User, User.id == Job.employer_id)
            .where(
                User.organization_id == organization_id,
                FitScoringCost.created_at >= start,
            )
        )
        return (await self._db.execute(stmt)).scalar_one()

    async def cv_uploads(self, organization_id: uuid.UUID | None) -> Allowance:
        limit, _ = await self._limits(organization_id)
        start, next_start = month_window()
        used = 0 if limit is None else await self._count_uploads(organization_id, start)
        return Allowance("CV uploads", limit, used, next_start)

    async def ai_scores(self, organization_id: uuid.UUID | None) -> Allowance:
        _, limit = await self._limits(organization_id)
        start, next_start = month_window()
        used = 0 if limit is None else await self._count_scores(organization_id, start)
        return Allowance("AI scores", limit, used, next_start)

    async def may_score(
        self,
        organization_id: uuid.UUID | None,
        job_id: uuid.UUID,
        *,
        application_id: uuid.UUID | None = None,
        talent_pool_profile_id: uuid.UUID | None = None,
    ) -> bool:
        """Whether the company may have this candidate AI-scored against this job now.

        Yes while this month's AI-scoring allowance has room. When it is spent, only a
        candidate who was already scored on this job THIS month (a retry, or a rescore):
        that adds no new score, so it must not be blocked.
        """
        allowance = await self.ai_scores(organization_id)
        if not allowance.exhausted:
            return True
        # Starter has no AI scores (a limit of 0), except on its free taste: the company's
        # first job, once the company is verified. What bounds that is the taste job's own
        # 10 applicants and the 10 uploads a month, not this meter.
        if organization_id is not None:
            plan = await BillingService(self._db).get_effective_plan(organization_id)
            if plan.code == "starter" and await is_taste_job(
                self._db, organization_id, job_id
            ):
                return True
        start, _ = month_window()
        same_candidate = (
            FitScoringCost.application_id == application_id
            if application_id is not None
            else FitScoringCost.talent_pool_profile_id == talent_pool_profile_id
        )
        stmt = select(func.count(FitScoringCost.id)).where(
            FitScoringCost.job_id == job_id,
            FitScoringCost.created_at >= start,
            same_candidate,
        )
        return (await self._db.execute(stmt)).scalar_one() > 0

    async def require_cv_upload(self, organization_id: uuid.UUID | None) -> None:
        """Raise ``PlanLimitReachedException`` when the company has used this month's uploads."""
        allowance = await self.cv_uploads(organization_id)
        if allowance.exhausted:
            raise PlanLimitReachedException(allowance.message())
