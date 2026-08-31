"""Business logic for the interview list."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobNotFoundError,
    NotFoundException,
    PermissionDeniedException,
)
from app.modules.interview_list.repository import InterviewListRepository
from app.modules.interview_list.schemas import (
    InterviewListEntryResponse,
    InterviewListIdsResponse,
    InterviewListResponse,
)


class InterviewListService:
    """Orchestrates adding/removing candidates from a job's interview list."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = InterviewListRepository(db)

    async def _verify_job_ownership(self, employer_id: uuid.UUID, job_id: uuid.UUID):
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        if job.employer_id != employer_id:
            raise PermissionDeniedException("You do not own this job")
        return job

    async def _resolve_talent_pool_profile_id(
        self,
        talent_pool_profile_id: uuid.UUID | None,
        candidate_profile_id: uuid.UUID | None,
    ) -> uuid.UUID:
        if talent_pool_profile_id:
            return talent_pool_profile_id

        from app.modules.talent_pool.repository import TalentPoolRepository

        profile = await TalentPoolRepository(self._db).get_by_candidate_profile_id(
            candidate_profile_id
        )
        if not profile:
            raise NotFoundException("Candidate profile not found")
        return profile.id

    async def add(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID | None,
        candidate_profile_id: uuid.UUID | None,
        note: str | None,
    ) -> uuid.UUID:
        """Add a candidate to a job's interview list. Commits.

        If the job has an AI video interview configured, this is also the
        invite trigger — being added here is what grants interview access
        (see Interview model docstring), regardless of whether the
        candidate has an Elevare account or ever submitted an Application.

        Returns the resolved ``talent_pool_profile_id`` — callers that only
        had a ``candidate_profile_id`` on hand need this to then call the
        send-invite endpoint, which is keyed on talent_pool_profile_id.
        """
        await self._verify_job_ownership(employer_id, job_id)
        resolved_id = await self._resolve_talent_pool_profile_id(
            talent_pool_profile_id, candidate_profile_id
        )
        await self._repo.add(employer_id, resolved_id, job_id, note)
        await self._db.commit()

        return resolved_id

    async def remove(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID | None,
        candidate_profile_id: uuid.UUID | None = None,
    ) -> None:
        """Remove a candidate from a job's interview list. Commits."""
        resolved_id = await self._resolve_talent_pool_profile_id(
            talent_pool_profile_id, candidate_profile_id
        )
        removed = await self._repo.remove(employer_id, resolved_id, job_id)
        await self._db.commit()
        if not removed:
            raise NotFoundException("This candidate isn't on this job's interview list")

    async def list_ids(
        self, employer_id: uuid.UUID, job_id: uuid.UUID
    ) -> InterviewListIdsResponse:
        ids = await self._repo.list_ids(employer_id, job_id)
        candidate_profile_ids = await self._repo.list_candidate_profile_ids(
            employer_id, job_id
        )
        return InterviewListIdsResponse(
            talent_pool_profile_ids=ids,
            candidate_profile_ids=candidate_profile_ids,
        )

    async def list_for_job(
        self, employer_id: uuid.UUID, job_id: uuid.UUID
    ) -> InterviewListResponse:
        """Return the interview list for one job, enriched for display."""
        from app.modules.talent_pool.service import resolve_match_display_fields
        from app.modules.interviews.repository import InterviewRepository

        entries = await self._repo.list_for_job(employer_id, job_id)

        from app.modules.introductions.repository import IntroductionRepository

        intro_repo = IntroductionRepository(self._db)
        interview_statuses = await InterviewRepository(self._db).list_statuses_for_job(
            job_id, [entry.talent_pool_profile_id for entry in entries]
        )

        items = []
        for entry in entries:
            profile = entry.talent_pool_profile
            fields = await resolve_match_display_fields(self._db, profile, employer_id)

            if profile.candidate_profile_id:
                ownership = "self_registered"
                has_cv_access = True
            elif profile.added_by == employer_id:
                ownership = "own_sourced"
                has_cv_access = True
            else:
                ownership = "admin_sourced"
                has_cv_access = await intro_repo.has_accepted_introduction(
                    employer_id=employer_id, talent_pool_profile_id=profile.id
                )

            items.append(
                InterviewListEntryResponse(
                    id=entry.id,
                    job_id=entry.job_id,
                    talent_pool_profile_id=profile.id,
                    candidate_profile_id=profile.candidate_profile_id,
                    ownership=ownership,
                    has_cv_access=has_cv_access,
                    candidate_name=fields["name"],
                    current_title=fields["current_title"],
                    location=fields["location"],
                    years_of_experience=fields["years_of_experience"],
                    skills=fields["skills"] or [],
                    note=entry.note,
                    added_at=entry.created_at,
                    interview_status=interview_statuses.get(profile.id),
                )
            )

        return InterviewListResponse(items=items, total=len(items))
