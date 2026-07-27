"""Business logic for saved candidates."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.saved_candidates.repository import SavedCandidateRepository
from app.modules.saved_candidates.schemas import (
    SavedCandidateIdsResponse,
    SavedCandidateListResponse,
    SavedCandidateResponse,
)


class SavedCandidateService:
    """Orchestrates saving/unsaving candidates and listing an employer's saved list."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = SavedCandidateRepository(db)

    async def _resolve_talent_pool_profile_id(
        self,
        talent_pool_profile_id: uuid.UUID | None,
        candidate_profile_id: uuid.UUID | None,
    ) -> uuid.UUID:
        """Resolve whichever id was given to the real talent_pool_profile_id."""
        if talent_pool_profile_id:
            return talent_pool_profile_id

        from app.modules.talent_pool.repository import TalentPoolRepository

        profile = await TalentPoolRepository(self._db).get_by_candidate_profile_id(
            candidate_profile_id
        )
        if not profile:
            raise NotFoundException("Candidate profile not found")
        return profile.id

    async def save(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID | None,
        candidate_profile_id: uuid.UUID | None,
        note: str | None,
    ) -> None:
        """Save a candidate (or update their note if already saved). Commits."""
        resolved_id = await self._resolve_talent_pool_profile_id(
            talent_pool_profile_id, candidate_profile_id
        )
        await self._repo.save(employer_id, resolved_id, note)
        await self._db.commit()

    async def unsave(
        self,
        employer_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID | None,
        candidate_profile_id: uuid.UUID | None = None,
    ) -> None:
        """Remove a saved candidate. Commits."""
        resolved_id = await self._resolve_talent_pool_profile_id(
            talent_pool_profile_id, candidate_profile_id
        )
        removed = await self._repo.unsave(employer_id, resolved_id)
        await self._db.commit()
        if not removed:
            raise NotFoundException("This candidate isn't in your saved list")

    async def list_ids(self, employer_id: uuid.UUID) -> SavedCandidateIdsResponse:
        """Return just the saved profile ids — cheap heart-state check for result cards."""
        ids = await self._repo.list_ids(employer_id)
        candidate_profile_ids = await self._repo.list_candidate_profile_ids(employer_id)
        return SavedCandidateIdsResponse(
            talent_pool_profile_ids=ids,
            candidate_profile_ids=candidate_profile_ids,
        )

    async def list_for_employer(
        self, employer_id: uuid.UUID
    ) -> SavedCandidateListResponse:
        """Return the employer's full saved-candidates list, enriched for display."""
        from app.modules.talent_pool.service import resolve_match_display_fields

        entries = await self._repo.list_for_employer(employer_id)

        items = []
        for entry in entries:
            profile = entry.talent_pool_profile
            fields = await resolve_match_display_fields(self._db, profile, employer_id)

            if profile.candidate_profile_id:
                ownership = "self_registered"
            elif profile.added_by == employer_id:
                ownership = "own_sourced"
            else:
                ownership = "admin_sourced"

            items.append(
                SavedCandidateResponse(
                    id=entry.id,
                    talent_pool_profile_id=profile.id,
                    candidate_profile_id=profile.candidate_profile_id,
                    ownership=ownership,
                    candidate_name=fields["name"],
                    current_title=fields["current_title"],
                    location=fields["location"],
                    years_of_experience=fields["years_of_experience"],
                    skills=fields["skills"] or [],
                    note=entry.note,
                    saved_at=entry.created_at,
                )
            )

        return SavedCandidateListResponse(items=items, total=len(items))
