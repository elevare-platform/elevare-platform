"""Data-access layer for the interview list."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.candidates.models import CandidateProfile
from app.modules.interview_list.models import InterviewListEntry
from app.modules.talent_pool.models import TalentPoolProfiles


class InterviewListRepository:
    """Handles database operations for :class:`InterviewListEntry`."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> InterviewListEntry | None:
        result = await self._db.execute(
            select(InterviewListEntry).where(
                InterviewListEntry.employer_id == employer_id,
                InterviewListEntry.talent_pool_profile_id == talent_pool_profile_id,
                InterviewListEntry.job_id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def add(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        job_id: uuid.UUID,
        note: str | None,
    ) -> InterviewListEntry:
        """Add a candidate to a job's interview list, or update the note if already added."""
        existing = await self.get(employer_id, talent_pool_profile_id, job_id)
        if existing:
            if note is not None:
                existing.note = note
                await self._db.flush()
            return existing

        entry = InterviewListEntry(
            employer_id=employer_id,
            talent_pool_profile_id=talent_pool_profile_id,
            job_id=job_id,
            note=note,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def remove(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> bool:
        existing = await self.get(employer_id, talent_pool_profile_id, job_id)
        if not existing:
            return False
        await self._db.delete(existing)
        await self._db.flush()
        return True

    async def list_ids(
        self, employer_id: uuid.UUID, job_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await self._db.execute(
            select(InterviewListEntry.talent_pool_profile_id).where(
                InterviewListEntry.employer_id == employer_id,
                InterviewListEntry.job_id == job_id,
            )
        )
        return [row[0] for row in result.all()]

    async def list_candidate_profile_ids(
        self, employer_id: uuid.UUID, job_id: uuid.UUID
    ) -> list[uuid.UUID]:
        result = await self._db.execute(
            select(TalentPoolProfiles.candidate_profile_id)
            .join(
                InterviewListEntry,
                InterviewListEntry.talent_pool_profile_id == TalentPoolProfiles.id,
            )
            .where(
                InterviewListEntry.employer_id == employer_id,
                InterviewListEntry.job_id == job_id,
                TalentPoolProfiles.candidate_profile_id.is_not(None),
            )
        )
        return [row[0] for row in result.all()]

    async def is_profile_invited(
        self, job_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> bool:
        """Return True if this talent pool profile is currently on this
        job's interview list — unlike is_candidate_invited, needs no
        candidate_profile_id, so it also works for sourced/parsed-only
        profiles with no Elevare account. No employer_id filter needed —
        an entry can only exist under the job's real owner, since add()
        verifies job ownership before insert."""
        result = await self._db.execute(
            select(InterviewListEntry.id).where(
                InterviewListEntry.job_id == job_id,
                InterviewListEntry.talent_pool_profile_id == talent_pool_profile_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def is_candidate_invited(
        self, job_id: uuid.UUID, candidate_profile_id: uuid.UUID
    ) -> bool:
        """Return True if this candidate has been added to this job's interview list.

        No employer_id filter needed — an entry can only exist for the
        job's actual owner, since ``add()`` verifies job ownership before
        insert.
        """
        result = await self._db.execute(
            select(InterviewListEntry.id)
            .join(
                TalentPoolProfiles,
                InterviewListEntry.talent_pool_profile_id == TalentPoolProfiles.id,
            )
            .where(
                InterviewListEntry.job_id == job_id,
                TalentPoolProfiles.candidate_profile_id == candidate_profile_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_invited_job_ids(
        self, candidate_profile_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """Return every job_id this candidate has been added to the interview list for."""
        result = await self._db.execute(
            select(InterviewListEntry.job_id)
            .join(
                TalentPoolProfiles,
                InterviewListEntry.talent_pool_profile_id == TalentPoolProfiles.id,
            )
            .where(TalentPoolProfiles.candidate_profile_id == candidate_profile_id)
        )
        return {row[0] for row in result.all()}

    async def list_for_job(
        self, employer_id: uuid.UUID, job_id: uuid.UUID
    ) -> list[InterviewListEntry]:
        result = await self._db.execute(
            select(InterviewListEntry)
            .where(
                InterviewListEntry.employer_id == employer_id,
                InterviewListEntry.job_id == job_id,
            )
            .options(
                selectinload(InterviewListEntry.talent_pool_profile)
                .selectinload(TalentPoolProfiles.candidate_profile)
                .selectinload(CandidateProfile.user),
                selectinload(InterviewListEntry.talent_pool_profile).selectinload(
                    TalentPoolProfiles.parsed_submission
                ),
            )
            .order_by(InterviewListEntry.created_at.desc())
        )
        return list(result.scalars().all())
