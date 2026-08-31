"""Data-access layer for saved candidates."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.candidates.models import CandidateProfile
from app.modules.saved_candidates.models import SavedCandidate
from app.modules.talent_pool.models import TalentPoolProfiles


class SavedCandidateRepository:
    """Handles database operations for :class:`SavedCandidate`."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(
        self, employer_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> SavedCandidate | None:
        """Return the saved-candidate row for this employer+profile pair, if any."""
        result = await self._db.execute(
            select(SavedCandidate).where(
                SavedCandidate.employer_id == employer_id,
                SavedCandidate.talent_pool_profile_id == talent_pool_profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def save(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        note: str | None,
    ) -> SavedCandidate:
        """Save a candidate, or update the note if already saved (idempotent)."""
        existing = await self.get(employer_id, talent_pool_profile_id)
        if existing:
            if note is not None:
                existing.note = note
                await self._db.flush()
            return existing

        entry = SavedCandidate(
            employer_id=employer_id,
            talent_pool_profile_id=talent_pool_profile_id,
            note=note,
        )
        self._db.add(entry)
        await self._db.flush()
        return entry

    async def unsave(
        self, employer_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> bool:
        """Remove a saved candidate. Returns False if it wasn't saved."""
        existing = await self.get(employer_id, talent_pool_profile_id)
        if not existing:
            return False
        await self._db.delete(existing)
        await self._db.flush()
        return True

    async def list_ids(self, employer_id: uuid.UUID) -> list[uuid.UUID]:
        """Return just the talent_pool_profile_ids this employer has saved."""
        result = await self._db.execute(
            select(SavedCandidate.talent_pool_profile_id).where(
                SavedCandidate.employer_id == employer_id
            )
        )
        return [row[0] for row in result.all()]

    async def list_candidate_profile_ids(
        self, employer_id: uuid.UUID
    ) -> list[uuid.UUID]:
        """Return the candidate_profile_ids of saved candidates that have one.

        Lets callers who only have a `candidate_profile_id` on hand (e.g.
        the applicants list) check saved-state without needing the
        underlying talent_pool_profile_id too.
        """
        result = await self._db.execute(
            select(TalentPoolProfiles.candidate_profile_id)
            .join(
                SavedCandidate,
                SavedCandidate.talent_pool_profile_id == TalentPoolProfiles.id,
            )
            .where(
                SavedCandidate.employer_id == employer_id,
                TalentPoolProfiles.candidate_profile_id.is_not(None),
            )
        )
        return [row[0] for row in result.all()]

    async def list_for_employer(self, employer_id: uuid.UUID) -> list[SavedCandidate]:
        """Return all saved candidates for an employer, newest first, with profile data loaded."""
        result = await self._db.execute(
            select(SavedCandidate)
            .where(SavedCandidate.employer_id == employer_id)
            .options(
                selectinload(SavedCandidate.talent_pool_profile)
                .selectinload(TalentPoolProfiles.candidate_profile)
                .selectinload(CandidateProfile.user),
                selectinload(SavedCandidate.talent_pool_profile).selectinload(
                    TalentPoolProfiles.parsed_submission
                ),
            )
            .order_by(SavedCandidate.created_at.desc())
        )
        return list(result.scalars().all())
