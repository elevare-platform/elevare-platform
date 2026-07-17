"""Data-access layer for introduction requests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.introductions.enums import IntroductionStatus
from app.modules.introductions.models import IntroductionRequest


class IntroductionRepository:
    """Queries and mutations for introduction_requests."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        token: str,
        expires_at: datetime,
    ) -> IntroductionRequest:
        """Create a new PENDING introduction request. Does NOT commit."""
        row = IntroductionRequest(
            employer_id=employer_id,
            job_id=job_id,
            talent_pool_profile_id=talent_pool_profile_id,
            status=IntroductionStatus.PENDING.value,
            token=token,
            expires_at=expires_at,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    async def get_by_token(self, token: str) -> IntroductionRequest | None:
        """Fetch by token with lazy expiry — flips PENDING→EXPIRED if past expires_at.

        Does NOT commit. Caller must commit if status was changed.
        """
        stmt = (
            select(IntroductionRequest)
            .where(IntroductionRequest.token == token)
            .options(selectinload(IntroductionRequest.employer))
        )
        result = await self._db.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        if (
            row.status == IntroductionStatus.PENDING.value
            and row.expires_at < datetime.now(UTC)
        ):
            row.status = IntroductionStatus.EXPIRED.value
            await self._db.flush()

        return row

    async def get_pending_for_profile(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> IntroductionRequest | None:
        """Return an active PENDING request for this employer+profile+job, if any."""
        stmt = select(IntroductionRequest).where(
            IntroductionRequest.employer_id == employer_id,
            IntroductionRequest.talent_pool_profile_id == talent_pool_profile_id,
            IntroductionRequest.job_id == job_id,
            IntroductionRequest.status == IntroductionStatus.PENDING.value,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_employer(
        self, employer_id: uuid.UUID
    ) -> tuple[list[IntroductionRequest], list[IntroductionRequest]]:
        """Return (all requests, newly-expired requests) for an employer.

        Lazily flips stale PENDING rows to EXPIRED. The second element lets
        the caller refund credits exactly once per row — a row only appears
        there the one time its expiry is first detected, never on repeat
        calls once it's already EXPIRED.

        Eager-loads job + talent_pool_profile (+ its candidate_profile/user
        and parsed_submission) so callers can build enriched responses
        without extra queries.
        """
        from app.modules.candidates.models import CandidateProfile
        from app.modules.talent_pool.models import TalentPoolProfiles

        stmt = (
            select(IntroductionRequest)
            .where(IntroductionRequest.employer_id == employer_id)
            .order_by(IntroductionRequest.created_at.desc())
            .options(
                selectinload(IntroductionRequest.job),
                selectinload(IntroductionRequest.talent_pool_profile)
                .selectinload(TalentPoolProfiles.candidate_profile)
                .selectinload(CandidateProfile.user),
                selectinload(IntroductionRequest.talent_pool_profile).selectinload(
                    TalentPoolProfiles.parsed_submission
                ),
            )
        )
        result = await self._db.execute(stmt)
        rows = list(result.scalars().unique().all())

        now = datetime.now(UTC)
        newly_expired = []
        for row in rows:
            if row.status == IntroductionStatus.PENDING.value and row.expires_at < now:
                row.status = IntroductionStatus.EXPIRED.value
                newly_expired.append(row)
                await self._db.flush()

        return rows, newly_expired

    async def mark_accepted(self, row: IntroductionRequest) -> IntroductionRequest:
        """Mark a request ACCEPTED. Does NOT commit."""
        row.status = IntroductionStatus.ACCEPTED.value
        row.responded_at = datetime.now(UTC)
        await self._db.flush()
        return row

    async def mark_declined(self, row: IntroductionRequest) -> IntroductionRequest:
        """Mark a request DECLINED. Does NOT commit."""
        row.status = IntroductionStatus.DECLINED.value
        row.responded_at = datetime.now(UTC)
        await self._db.flush()
        return row
