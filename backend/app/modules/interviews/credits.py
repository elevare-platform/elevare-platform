"""Giving an AI interview's credits back.

Used by the background task when an interview's pipeline fails for good, and by the
hourly sweep for an invite that expired without the candidate opening it. The
charge itself is taken at the invite (see ``InterviewService._charge_for_invite``).
"""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.credits.service import CreditsService
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import Interview
from app.modules.interviews.repository import InterviewRepository
from app.modules.users.enums import UserRole


def _paying_organization_id(interview: Interview) -> uuid.UUID | None:
    """The organization that paid for the interview, or None when nobody did:
    Elevare's own admin-owned jobs and owners with no organization are not
    charged, so there is nothing to give back."""
    employer = interview.job.employer if interview.job else None
    if (
        employer is None
        or employer.role == UserRole.ADMIN.value
        or employer.organization_id is None
    ):
        return None
    return employer.organization_id


def is_unused_and_expired(interview: Interview, now: datetime) -> bool:
    """Whether the invite expired and the candidate never started the interview."""
    return (
        interview.status == InterviewStatus.PENDING.value
        and interview.token_expires_at is not None
        and interview.token_expires_at < now
        and interview.session_start_count == 0
    )


async def refund_interview_credits(db: AsyncSession, interview_id: uuid.UUID) -> int:
    """Give back what an interview was charged, once. Returns the credits
    returned (0 when it was never charged, was refunded already, or nobody paid).

    Does not commit: the caller owns the transaction.
    """
    interview = await InterviewRepository(db).get_by_id(interview_id)
    if interview is None:
        return 0
    organization_id = _paying_organization_id(interview)
    if organization_id is None:
        return 0
    return await CreditsService(db).refund_interview(organization_id, interview.id)


async def refund_if_unused(
    db: AsyncSession, interview_id: uuid.UUID, now: datetime
) -> int:
    """Refund an interview whose invite expired unopened, re-checking under the
    interview's own lock.

    The sweep picks its candidates a moment before it refunds them. If the
    employer resends the invite in between, the interview is valid again and must
    keep its charge; a resend takes the same lock before deciding whether to
    charge, so the two always take turns and each sees the other's result.

    Does not commit: the caller owns the transaction.
    """
    repo = InterviewRepository(db)
    await repo.lock_status(interview_id)
    interview = await repo.get_by_id(interview_id)
    if interview is None:
        return 0
    # The row was locked and may have changed since it was loaded.
    await db.refresh(interview)
    if not is_unused_and_expired(interview, now):
        return 0
    return await refund_interview_credits(db, interview_id)
