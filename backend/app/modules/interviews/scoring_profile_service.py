"""A job's scoring profile: read it, save it, remove it (docs/08_DECISIONS.md, item 36).

Access follows the shared ownership rule (decision D2): anyone in the company that owns the job.
The rules (what makes a profile valid, how a score is worked out) are in ``scoring_profile.py``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedException, ValidationException
from app.core.ownership import can_manage_job
from app.core.schema_guard import tolerate_missing
from app.modules.interviews import scoring_profile as rules
from app.modules.interviews.models import JobInterviewQuestion, JobScoringProfile
from app.modules.jobs.repository import JobRepository
from app.modules.users.models import User


async def load_profile(db: AsyncSession, job_id: uuid.UUID) -> JobScoringProfile | None:
    """The job's scoring profile, or None when it has none (it is then scored by the generic
    scorecard). Also None in the seconds of a deploy before the migration that creates the table
    has run, so a page or a scoring run does not fail for it."""

    async def read() -> JobScoringProfile | None:
        result = await db.execute(select(JobScoringProfile).where(JobScoringProfile.job_id == job_id))
        return result.scalar_one_or_none()

    return await tolerate_missing(db, read, None)


def profile_out(profile: JobScoringProfile | None) -> dict | None:
    """The profile as the API shows it."""
    if profile is None:
        return None
    return {
        "competencies": profile.competencies,
        "bands": profile.bands,
        "key_min_rating": profile.key_min_rating,
        "template_code": profile.template_code,
    }


class ScoringProfileService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _job_for(self, user: User, job_id: uuid.UUID):
        job = await JobRepository(self._db).get_by_id(job_id)  # raises JobNotFoundError
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        return job

    @staticmethod
    def _response(profile: JobScoringProfile | None) -> dict:
        return {
            "profile": profile_out(profile),
            "templates": rules.TEMPLATES,
            "default_bands": rules.DEFAULT_BANDS,
            "default_key_min_rating": rules.DEFAULT_KEY_MIN_RATING,
        }

    async def get(self, user: User, job_id: uuid.UUID) -> dict:
        await self._job_for(user, job_id)
        return self._response(await load_profile(self._db, job_id))

    async def save(
        self,
        user: User,
        job_id: uuid.UUID,
        competencies: list[dict],
        bands: dict | None,
        key_min_rating: int,
        template_code: str | None,
        commit: bool = True,
    ) -> dict:
        """Save the job's scoring profile, all or nothing, refused with every problem named if it
        breaks a rule. A question tagged with a competency the new profile no longer has loses its
        tag (the employer sees it as untagged). ``commit=False`` leaves the transaction open, for a
        caller that saves something else with it and commits once."""
        await self._job_for(user, job_id)
        # "AUTO" marks a profile the system built for the role; only it can set that, so a profile
        # the employer saves is theirs (they may have started from one and changed it).
        if template_code == "AUTO":
            template_code = None
        bands = bands or dict(rules.DEFAULT_BANDS)
        problems = rules.problems_with(competencies, bands, key_min_rating)
        if problems:
            raise ValidationException(
                message=" ".join(problems),
                details=[{"field": "scoring_profile", "message": problem} for problem in problems],
            )
        tidy = rules.tidy(competencies)
        profile = await load_profile(self._db, job_id)
        if profile is None:
            profile = JobScoringProfile(job_id=job_id, competencies=tidy, bands=bands,
                                        key_min_rating=key_min_rating, template_code=template_code)
            self._db.add(profile)
        else:
            profile.competencies = tidy
            profile.bands = bands
            profile.key_min_rating = key_min_rating
            profile.template_code = template_code
        await self._db.flush()
        await self._clear_dangling_tags(job_id, [item["name"] for item in tidy])
        if commit:
            await self._db.commit()
        await self._db.refresh(profile)
        return self._response(profile)

    async def remove(self, user: User, job_id: uuid.UUID) -> dict:
        """Take the profile off the job: it goes back to the generic scorecard, and its questions
        lose their tags. Interviews already scored keep their reports."""
        await self._job_for(user, job_id)
        profile = await load_profile(self._db, job_id)
        if profile is not None:
            await self._db.delete(profile)
            await self._clear_dangling_tags(job_id, [])
        await self._db.commit()
        return self._response(None)

    async def _clear_dangling_tags(self, job_id: uuid.UUID, names: list[str]) -> None:
        keep = {name.casefold() for name in names}
        result = await self._db.execute(
            select(JobInterviewQuestion).where(
                JobInterviewQuestion.job_id == job_id, JobInterviewQuestion.competency.is_not(None)
            )
        )
        for question in result.scalars().all():
            if question.competency.casefold() not in keep:
                question.competency = None
        await self._db.flush()


def untested(competencies: list[dict], tags: list[str | None]) -> list[str]:
    """The profile's competencies that no question is tagged with, in the profile's order."""
    tagged = {tag.casefold() for tag in tags if tag}
    return [item["name"] for item in competencies if item["name"].casefold() not in tagged]


def canonical_tag(tag: str | None, competencies: list[dict]) -> str | None:
    """The profile's own spelling of a tag, or None when it is not one of its competencies."""
    if not tag:
        return None
    wanted = rules.clean_name(tag).casefold()
    return next((item["name"] for item in competencies if item["name"].casefold() == wanted), None)


__all__ = ["ScoringProfileService", "canonical_tag", "load_profile", "profile_out", "untested"]
