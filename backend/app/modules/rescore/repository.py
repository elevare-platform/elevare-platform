"""Queries for candidates on one job who have no usable score."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import ParsedCVSubmission
from app.modules.applications.models import Application
from app.modules.candidates.models import CandidateCvs
from app.modules.jobs.models import Job
from app.modules.talent_pool.models import TalentPoolProfiles

# Without a failure marker and without a score, a candidate is normally just waiting
# for scoring to finish. After this long it has been forgotten (an application scored
# while its CV was still being read used to be skipped for good), so it counts too.
# A rescore bumps updated_at, so a candidate just put back in the queue is not picked
# up a second time.
STUCK_AFTER = timedelta(hours=1)


def _needs_rescore(model, now: datetime):
    """The candidate has no real score: a failure marker, a score of 0 with no summary
    (the shape older code saved when a call failed), or unscored for a long time.
    A candidate with a genuine score never matches."""
    return or_(
        model.ai_score_failure.is_not(None),
        and_(
            model.ai_score == 0,
            or_(model.ai_fit_summary.is_(None), model.ai_fit_summary == ""),
        ),
        and_(
            model.ai_score.is_(None),
            model.updated_at < now - STUCK_AFTER,
        ),
    )


class RescoreRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def lock_job(self, job_id: uuid.UUID) -> None:
        """Hold the job's row until the transaction ends, so two people pressing Rescore
        for the same job at once take turns: the second finds the first one's work
        already done instead of queueing it again."""
        await self._db.execute(select(Job.id).where(Job.id == job_id).with_for_update())

    def _applications(self, job_id: uuid.UUID, now: datetime):
        return (
            select(Application)
            .where(
                Application.job_id == job_id,
                Application.cv_id.is_not(None),
                Application.status != "WITHDRAWN",
                _needs_rescore(Application, now),
            )
            .order_by(Application.updated_at.asc(), Application.id)
        )

    def _pipeline(self, job_id: uuid.UUID, now: datetime):
        return (
            select(TalentPoolProfiles)
            .where(
                TalentPoolProfiles.sourced_for_job_id == job_id,
                TalentPoolProfiles.parsed_submission_id.is_not(None),
                _needs_rescore(TalentPoolProfiles, now),
            )
            .order_by(TalentPoolProfiles.updated_at.asc(), TalentPoolProfiles.id)
        )

    async def count_applications(self, job_id: uuid.UUID, now: datetime) -> int:
        query = self._applications(job_id, now).order_by(None)
        return (
            await self._db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar_one()

    async def count_pipeline(self, job_id: uuid.UUID, now: datetime) -> int:
        query = self._pipeline(job_id, now).order_by(None)
        return (
            await self._db.execute(select(func.count()).select_from(query.subquery()))
        ).scalar_one()

    async def applications_needing(
        self, job_id: uuid.UUID, now: datetime, limit: int
    ) -> list[Application]:
        result = await self._db.execute(self._applications(job_id, now).limit(limit))
        return list(result.scalars().all())

    async def pipeline_needing(
        self, job_id: uuid.UUID, now: datetime, limit: int
    ) -> list[TalentPoolProfiles]:
        result = await self._db.execute(self._pipeline(job_id, now).limit(limit))
        return list(result.scalars().all())

    async def get_application(
        self, job_id: uuid.UUID, application_id: uuid.UUID
    ) -> Application | None:
        """The application, only if it belongs to this job."""
        result = await self._db.execute(
            select(Application).where(
                Application.id == application_id, Application.job_id == job_id
            )
        )
        return result.scalar_one_or_none()

    async def get_pipeline_profile(
        self, job_id: uuid.UUID, profile_id: uuid.UUID
    ) -> TalentPoolProfiles | None:
        """The pipeline profile, only if it was sourced for this job."""
        result = await self._db.execute(
            select(TalentPoolProfiles).where(
                TalentPoolProfiles.id == profile_id,
                TalentPoolProfiles.sourced_for_job_id == job_id,
            )
        )
        return result.scalar_one_or_none()

    async def submission_for_application(
        self, application: Application
    ) -> ParsedCVSubmission | None:
        result = await self._db.execute(
            select(ParsedCVSubmission)
            .join(CandidateCvs, CandidateCvs.submission_id == ParsedCVSubmission.id)
            .where(CandidateCvs.id == application.cv_id)
        )
        return result.scalar_one_or_none()

    async def submission_for_profile(
        self, profile: TalentPoolProfiles
    ) -> ParsedCVSubmission | None:
        result = await self._db.execute(
            select(ParsedCVSubmission).where(
                ParsedCVSubmission.id == profile.parsed_submission_id
            )
        )
        return result.scalar_one_or_none()
