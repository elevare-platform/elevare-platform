"""Switching a job off because of a plan rule (status DISABLED), and telling the employer.

Used when a job takes its last allowed applicant, when it has run its time, and when a plan
lapses. A disabled job keeps all of its applicants and can be re-published once the plan allows
it (see ``JobService.publish_job``).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.billing.service import BillingService
from app.modules.billing.starter_rules import STARTER_JOB_DAYS
from app.modules.jobs.enums import JobDisabledReason, JobStatus
from app.modules.jobs.models import Job
from app.modules.notifications.repository import NotificationRepository
from app.modules.users.enums import UserRole
from app.modules.users.models import User

logger = logging.getLogger(__name__)


def _words(job, reason: JobDisabledReason, detail: int | None) -> tuple[str, str]:
    """The notification title and body for each reason."""
    kept = "Your applicants are kept. Upgrade your plan to re-publish it."
    if reason == JobDisabledReason.APPLICANT_LIMIT:
        return (
            f"'{job.title}' reached its applicant limit",
            f"It received {detail} applicants, the most your plan allows for one job, so it has "
            f"been switched off. {kept}",
        )
    if reason == JobDisabledReason.EXPIRED:
        return (
            f"'{job.title}' has ended",
            f"Your plan runs a job for {detail} days, so it has been switched off. {kept}",
        )
    return (
        f"'{job.title}' has been switched off",
        f"Your plan has ended and the plan you are on now allows fewer jobs. {kept}",
    )


@dataclass(frozen=True)
class DisabledJob:
    """What the email about a switched-off job needs, kept until the switch-off is committed."""

    job_id: uuid.UUID
    title: str
    employer_email: str | None
    reason: JobDisabledReason
    detail: int | None


async def disable_job(
    db: AsyncSession, job, reason: JobDisabledReason, detail: int | None = None
) -> DisabledJob | None:
    """Switch a live job off and tell its owner in the app. Not committed: the caller commits.

    ``detail`` is the number the message quotes: the applicant limit, or the number of days.
    Does nothing for a job that is not ACTIVE (a closed job stays closed) and returns None.

    Returns what the email needs. The caller commits FIRST and then passes it to
    ``queue_disabled_emails``, so an email never goes out for a switch-off that did not save.
    """
    if job.status != JobStatus.ACTIVE.value:
        return None
    job.status = JobStatus.DISABLED.value
    job.disabled_reason = reason.value
    job.disabled_at = datetime.now(UTC)
    await db.flush()

    employer_email = None
    if job.employer_id is not None:
        title, body = _words(job, reason, detail)
        await NotificationRepository(db).create(
            recipient_id=job.employer_id,
            type="JOB_DISABLED",
            title=title,
            body=body,
            entity_type="JOB",
            entity_id=job.id,
        )
        employer = await db.get(User, job.employer_id)
        employer_email = employer.email if employer else None
    return DisabledJob(job.id, job.title, employer_email, reason, detail)


def queue_disabled_emails(disabled: list[DisabledJob | None]) -> None:
    """Send the "your job was switched off" email for each switch-off. Call AFTER the commit.

    A problem queueing an email (the broker is down) is logged and never raised: it must not
    fail the application or the sweep that switched the job off, and the employer has the
    in-app notification either way.
    """
    from app.modules.applications.tasks import send_job_switched_off_email

    for item in disabled:
        if item is None or not item.employer_email:
            continue
        try:
            send_job_switched_off_email.delay(
                item.employer_email,
                str(item.job_id),
                item.title,
                item.reason.value,
                item.detail,
            )
        except Exception:
            logger.exception("Could not queue the switched-off email for job %s", item.job_id)


async def disable_expired_starter_jobs(db: AsyncSession) -> int:
    """Switch off every live job of a Starter company that has run for ``STARTER_JOB_DAYS`` days.

    The other half of "whichever comes first" (the applicant limit is checked when someone
    applies). Run by the scheduler every hour; it does nothing while plan gating is switched
    off. The plan is read through ``get_effective_plan``, so a company on the exemption list
    keeps its jobs. Commits once per company, so one problem never undoes the others.
    Returns how many jobs were switched off.
    """
    if not settings.plan_gates_enabled:
        return 0
    cutoff = datetime.now(UTC) - timedelta(days=STARTER_JOB_DAYS)
    old_live = (
        Job.status == JobStatus.ACTIVE.value,
        Job.published_at <= cutoff,
        Job.is_general_interest.is_(False),
    )

    # Companies, not jobs: a company on a paid plan may have any number of old live jobs, and
    # taking "the oldest N jobs" would let those crowd out a Starter company's.
    organization_ids = (
        (
            await db.execute(
                select(User.organization_id)
                .join(Job, Job.employer_id == User.id)
                .where(*old_live, User.role != UserRole.ADMIN.value, User.organization_id.is_not(None))
                .distinct()
            )
        )
        .scalars()
        .all()
    )

    switched_off = 0
    billing = BillingService(db)
    for organization_id in organization_ids:
        plan = await billing.get_effective_plan(organization_id)
        if plan.code != "starter":
            continue
        jobs = (
            (
                await db.execute(
                    select(Job)
                    .join(User, User.id == Job.employer_id)
                    .where(*old_live, User.organization_id == organization_id)
                )
            )
            .scalars()
            .all()
        )
        disabled = [
            await disable_job(db, job, JobDisabledReason.EXPIRED, STARTER_JOB_DAYS)
            for job in jobs
        ]
        await db.commit()
        queue_disabled_emails(disabled)  # only now that the switch-off is saved
        switched_off += len([d for d in disabled if d is not None])
    if switched_off:
        logger.info("disable_expired_starter_jobs: switched off %d job(s)", switched_off)
    return switched_off
