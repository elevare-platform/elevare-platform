"""Business logic for introduction requests."""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobNotFoundError,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.modules.credits.service import CreditsService
from app.modules.introductions.enums import IntroductionStatus
from app.modules.introductions.repository import IntroductionRepository
from app.modules.introductions.schemas import (
    IntroductionRequestResponse,
    IntroductionSummaryResponse,
)
from app.modules.jobs.repository import JobRepository
from app.modules.talent_pool.repository import TalentPoolRepository

logger = logging.getLogger(__name__)

_TOKEN_EXPIRY_DAYS = 7


def _resolve_candidate_email(profile) -> str | None:
    """Resolve candidate email from either population.

    Self-registered → candidate_profile.user.email
    Sourced-only    → parsed_submission.parsed_data.email
    """
    if profile.candidate_profile and profile.candidate_profile.user:
        return profile.candidate_profile.user.email
    if profile.parsed_submission and profile.parsed_submission.parsed_data:
        return profile.parsed_submission.parsed_data.get("email")
    return None


def _resolve_display_name(profile, accepted: bool) -> str | None:
    """Return a display name only when the employer is allowed to see it."""
    if not accepted:
        return None
    if profile.candidate_profile and profile.candidate_profile.user:
        u = profile.candidate_profile.user
        return f"{u.first_name} {u.last_name}".strip() or None
    if profile.parsed_submission and profile.parsed_submission.parsed_data:
        pd = profile.parsed_submission.parsed_data
        return pd.get("full_name") or (
            f"{pd.get('first_name', '')} {pd.get('last_name', '')}".strip() or None
        )
    return None


def _resolve_current_title(profile) -> str | None:
    """Return current_title from parsed data regardless of visibility."""
    if profile.parsed_submission and profile.parsed_submission.parsed_data:
        return profile.parsed_submission.parsed_data.get("current_title")
    return None


class IntroductionService:
    """Orchestrates introduction request creation and response handling."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = IntroductionRepository(db)
        self._credits = CreditsService(db)

    async def request_introduction(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> IntroductionRequestResponse:
        """Create an introduction request, deduct 1 credit, dispatch email task. Commits."""
        job_repo = JobRepository(self._db)
        job = await job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        if job.employer_id != employer_id:
            raise PermissionDeniedException("You do not own this job")

        tp_repo = TalentPoolRepository(self._db)
        profile = await tp_repo.get_by_id_joined_with_parsed_data(
            talent_pool_profile_id
        )
        if not profile:
            raise NotFoundException("Talent pool profile not found")

        existing = await self._repo.get_pending_for_profile(
            employer_id=employer_id,
            talent_pool_profile_id=talent_pool_profile_id,
            job_id=job_id,
        )
        if existing:
            raise ValidationException(
                "An introduction request is already pending for this candidate"
            )

        candidate_email = _resolve_candidate_email(profile)
        if not candidate_email:
            raise ValidationException(
                "No email address available for this candidate — cannot send introduction request"
            )

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(days=_TOKEN_EXPIRY_DAYS)

        # Deduct first — raises ValidationException if balance = 0
        await self._credits.deduct(employer_id=employer_id)

        intro = await self._repo.create(
            employer_id=employer_id,
            job_id=job_id,
            talent_pool_profile_id=talent_pool_profile_id,
            token=token,
            expires_at=expires_at,
        )

        from app.core.config import settings
        from app.modules.introductions.tasks import send_introduction_request_email

        send_introduction_request_email.delay(
            candidate_email=candidate_email,
            accept_url=f"{settings.app_url}/introduction-response?token={token}&action=accept",
            decline_url=f"{settings.app_url}/introduction-response?token={token}&action=decline",
            job_title=job.title,
        )

        await self._db.commit()
        return IntroductionRequestResponse.model_validate(intro)

    async def accept(self, token: str) -> dict:
        """Process a candidate accept action via magic link. Commits."""
        intro = await self._repo.get_by_token(token)
        if not intro:
            raise NotFoundException("Introduction request not found")

        if intro.status == IntroductionStatus.EXPIRED.value:
            await self._credits.refund(
                employer_id=intro.employer_id, reference_id=intro.id
            )
            await self._db.commit()
            return {
                "status": "EXPIRED",
                "message": "This introduction request has expired",
            }

        if intro.status != IntroductionStatus.PENDING.value:
            return {
                "status": intro.status,
                "message": "This link has already been used",
            }

        await self._repo.mark_accepted(intro)

        from app.core.config import settings
        from app.modules.introductions.tasks import send_introduction_accepted_email

        send_introduction_accepted_email.delay(
            employer_email=intro.employer.email,
            job_title="a role",  # job not loaded in get_by_token — employer sees job context in dashboard
            profile_url=f"{settings.app_url}/employer/jobs/{intro.job_id}/applicants",
        )

        await self._db.commit()
        return {"status": "ACCEPTED", "message": "Introduction accepted"}

    async def decline(self, token: str) -> dict:
        """Process a candidate decline action via magic link. Refunds credit. Commits."""
        intro = await self._repo.get_by_token(token)
        if not intro:
            raise NotFoundException("Introduction request not found")

        if intro.status == IntroductionStatus.EXPIRED.value:
            await self._credits.refund(
                employer_id=intro.employer_id, reference_id=intro.id
            )
            await self._db.commit()
            return {
                "status": "EXPIRED",
                "message": "This introduction request has expired",
            }

        if intro.status != IntroductionStatus.PENDING.value:
            return {
                "status": intro.status,
                "message": "This link has already been used",
            }

        await self._repo.mark_declined(intro)
        await self._credits.refund(employer_id=intro.employer_id, reference_id=intro.id)

        from app.modules.introductions.tasks import send_introduction_declined_email

        send_introduction_declined_email.delay(
            employer_email=intro.employer.email,
            job_title="a role",  # job not loaded in get_by_token
        )

        await self._db.commit()
        return {"status": "DECLINED", "message": "Introduction declined"}

    async def list_for_profile(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> list[IntroductionRequestResponse]:
        """Return all intro requests for a specific employer+job+profile combination."""
        rows, newly_expired = await self._repo.list_for_employer(employer_id)
        await self._refund_newly_expired(newly_expired)
        rows = [
            r
            for r in rows
            if r.job_id == job_id and r.talent_pool_profile_id == talent_pool_profile_id
        ]
        return [IntroductionRequestResponse.model_validate(r) for r in rows]

    async def list_for_job(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> list[IntroductionRequestResponse]:
        """Return all intro requests this employer has made for a job."""
        rows, newly_expired = await self._repo.list_for_employer(employer_id)
        await self._refund_newly_expired(newly_expired)
        rows = [r for r in rows if r.job_id == job_id]
        return [IntroductionRequestResponse.model_validate(r) for r in rows]

    async def list_mine(
        self,
        employer_id: uuid.UUID,
    ) -> list[IntroductionSummaryResponse]:
        """Return all introduction requests this employer has ever made, across all jobs."""
        rows, newly_expired = await self._repo.list_for_employer(employer_id)
        await self._refund_newly_expired(newly_expired)

        items = []
        for row in rows:
            accepted = row.status == IntroductionStatus.ACCEPTED.value
            items.append(
                IntroductionSummaryResponse(
                    id=row.id,
                    job_id=row.job_id,
                    job_title=row.job.title if row.job else "",
                    talent_pool_profile_id=row.talent_pool_profile_id,
                    candidate_name=_resolve_display_name(
                        row.talent_pool_profile, accepted
                    ),
                    candidate_current_title=_resolve_current_title(
                        row.talent_pool_profile
                    ),
                    status=row.status,
                    created_at=row.created_at,
                    expires_at=row.expires_at,
                    responded_at=row.responded_at,
                )
            )
        return items

    async def _refund_newly_expired(self, newly_expired: list) -> None:
        """Refund credit for each request that just flipped PENDING→EXPIRED."""
        if not newly_expired:
            return
        for row in newly_expired:
            await self._credits.refund(employer_id=row.employer_id, reference_id=row.id)
        await self._db.commit()
