"""Data-access layer for AI video interviews."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.candidates.models import CandidateProfile
from app.modules.credits.models import CreditTransaction
from app.modules.credits.repository import INTERVIEW_CHARGE, INTERVIEW_REFUND
from app.modules.interviews.enums import InterviewStatus, compute_display_status
from app.modules.interviews.models import (
    Interview,
    InterviewCost,
    InterviewTranscriptCheck,
)
from app.modules.jobs.models import Job
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.users.models import User


class InterviewRepository:
    """Data-access layer for :class:`Interview` records."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session."""
        self._db = db

    def _base_options(self):
        return [
            selectinload(Interview.job)
            .selectinload(Job.employer)
            .selectinload(User.organization),
            # resolve_match_display_fields (called against
            # interview.talent_pool_profile once scoring finishes) reads
            # parsed_submission and candidate_profile.user — eager-load the
            # full chain here or the lazy load blows up under AsyncSession
            # with MissingGreenlet.
            selectinload(Interview.talent_pool_profile).selectinload(
                TalentPoolProfiles.parsed_submission
            ),
            selectinload(Interview.talent_pool_profile)
            .selectinload(TalentPoolProfiles.candidate_profile)
            .selectinload(CandidateProfile.user),
        ]

    async def get_by_id(self, interview_id: uuid.UUID) -> Interview | None:
        """Fetch an interview by its primary key, with job and profile eager-loaded."""
        stmt = (
            select(Interview)
            .where(Interview.id == interview_id)
            .options(*self._base_options())
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_job_and_profile(
        self, job_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> Interview | None:
        """Fetch the interview for a given job + talent pool profile, if one exists."""
        stmt = (
            select(Interview)
            .where(
                Interview.job_id == job_id,
                Interview.talent_pool_profile_id == talent_pool_profile_id,
            )
            .options(*self._base_options())
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Interview | None:
        """Fetch the interview matching an invite token, if one exists."""
        stmt = (
            select(Interview)
            .where(Interview.token == token)
            .options(*self._base_options())
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_statuses_for_job(
        self, job_id: uuid.UUID, talent_pool_profile_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """Batch-fetch display status per candidate for a job, keyed by talent_pool_profile_id.

        "Display status" folds in a not-yet-persisted EXPIRED — see
        ``compute_display_status``.
        """
        if not talent_pool_profile_ids:
            return {}
        stmt = select(
            Interview.talent_pool_profile_id, Interview.status, Interview.token_expires_at
        ).where(
            Interview.job_id == job_id,
            Interview.talent_pool_profile_id.in_(talent_pool_profile_ids),
        )
        result = await self._db.execute(stmt)
        return {
            row[0]: compute_display_status(row[1], row[2]) for row in result.all()
        }

    async def list_unfinished_failures_for_job(
        self, job_id: uuid.UUID, talent_pool_profile_ids: list[uuid.UUID]
    ) -> set[uuid.UUID]:
        """The candidates (by talent_pool_profile_id) whose interview is FAILED without ever
        having been completed: the recording never arrived, so nothing was scored. A FAILED
        interview with a completion time failed in scoring, which is a different problem."""
        if not talent_pool_profile_ids:
            return set()
        result = await self._db.execute(
            select(Interview.talent_pool_profile_id).where(
                Interview.job_id == job_id,
                Interview.talent_pool_profile_id.in_(talent_pool_profile_ids),
                Interview.status == InterviewStatus.FAILED.value,
                Interview.completed_at.is_(None),
            )
        )
        return {row[0] for row in result.all()}

    async def list_statuses_for_profile(
        self, talent_pool_profile_id: uuid.UUID, job_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, str]:
        """Batch-fetch display status per job for one candidate, keyed by job_id.

        "Display status" folds in a not-yet-persisted EXPIRED — see
        ``compute_display_status``.
        """
        if not job_ids:
            return {}
        stmt = select(
            Interview.job_id, Interview.status, Interview.token_expires_at
        ).where(
            Interview.talent_pool_profile_id == talent_pool_profile_id,
            Interview.job_id.in_(job_ids),
        )
        result = await self._db.execute(stmt)
        return {
            row[0]: compute_display_status(row[1], row[2]) for row in result.all()
        }

    async def list_expired_with_video(
        self, before: datetime, limit: int = 200
    ) -> list[Interview]:
        """Return interviews whose video retention window has passed and still
        have an R2 object attached — candidates for the retention sweep."""
        stmt = (
            select(Interview)
            .where(Interview.video_expires_at.is_not(None))
            .where(Interview.video_expires_at < before)
            .where(Interview.r2_key.is_not(None))
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_stale_in_progress_interviews(
        self,
        before: datetime,
        limit: int = 200,
        upload_before: datetime | None = None,
    ) -> list[Interview]:
        """Return interviews stuck IN_PROGRESS with no activity since
        `before` — abandoned mid-interview (closed tab, crashed browser),
        candidates for the reap sweep. Keyed off updated_at, not
        created_at/started_at: every real activity (session start/restart,
        upload, complete) bumps updated_at, so a truly abandoned
        interview's updated_at freezes at its last session start while a
        genuinely long-running one keeps moving.

        An interview that reached the upload step (it has a recording key,
        issued with the upload address) is waiting for its recording, so it
        is only returned once it has been idle since `upload_before`, which
        is later than `before`."""
        stmt = (
            select(Interview)
            .where(Interview.status == InterviewStatus.IN_PROGRESS.value)
            .where(Interview.updated_at < before)
            .limit(limit)
        )
        if upload_before is not None:
            stmt = stmt.where(
                or_(Interview.r2_key.is_(None), Interview.updated_at < upload_before)
            )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_unused_expired_paid_interview_ids(
        self, now: datetime, limit: int = 200
    ) -> list[uuid.UUID]:
        """Ids of interviews whose invite expired and was never opened, and which
        are still paid (charged and not refunded): the ones to give credits back
        for. Oldest first.

        An interview that was refunded stays PENDING and expired forever, so the
        "still paid" condition is part of the query itself: otherwise those rows
        would fill every batch and the sweep would never reach a newer one.
        """

        def count_of(reason: str):
            return (
                select(func.count())
                .select_from(CreditTransaction)
                .where(
                    CreditTransaction.reason == reason,
                    CreditTransaction.reference_id == Interview.id,
                )
                .correlate(Interview)
                .scalar_subquery()
            )

        stmt = (
            select(Interview.id)
            .where(
                Interview.status == InterviewStatus.PENDING.value,
                Interview.token_expires_at < now,
                Interview.session_start_count == 0,
                count_of(INTERVIEW_CHARGE) > count_of(INTERVIEW_REFUND),
            )
            .order_by(Interview.token_expires_at)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        application_id: uuid.UUID | None = None,
        interview_id: uuid.UUID | None = None,
    ) -> Interview:
        """Persist a new interview record and return it.

        ``interview_id`` lets a caller decide the id first, so it can charge the
        interview's credits before anything is saved.
        """
        interview = Interview(
            job_id=job_id,
            talent_pool_profile_id=talent_pool_profile_id,
            application_id=application_id,
        )
        if interview_id is not None:
            interview.id = interview_id
        self._db.add(interview)
        await self._db.flush()
        await self._db.refresh(interview)
        return interview

    async def update(self, interview_id: uuid.UUID, data: dict) -> Interview:
        """Apply a partial update dict to an interview and return the updated record."""
        interview = await self.get_by_id(interview_id)
        for key, value in data.items():
            setattr(interview, key, value)
        await self._db.flush()
        await self._db.refresh(interview)
        return interview

    async def lock_status(self, interview_id: uuid.UUID) -> str:
        """Lock the interview row until the transaction ends and return the
        status the database holds right now (not a possibly stale loaded copy).

        Serialises operations that must not run twice at once, such as
        completing an upload. Must be called inside the transaction that will
        make the change, so the lock is held until it commits.
        """
        result = await self._db.execute(
            select(Interview.status)
            .where(Interview.id == interview_id)
            .with_for_update()
        )
        return result.scalar_one()

    async def count_created_since(
        self,
        since: datetime,
        *,
        organization_id: uuid.UUID | None,
        employer_id: uuid.UUID,
    ) -> int:
        """Count interviews created since ``since`` for one paying party.

        The party is the job owner's organization or, for an account that has
        no organization (e.g. an Elevare admin), that account alone.
        """
        stmt = (
            select(func.count(Interview.id))
            .join(Job, Job.id == Interview.job_id)
            .join(User, User.id == Job.employer_id)
            .where(Interview.created_at >= since)
        )
        if organization_id is not None:
            stmt = stmt.where(User.organization_id == organization_id)
        else:
            stmt = stmt.where(Job.employer_id == employer_id)
        result = await self._db.execute(stmt)
        return result.scalar_one()

    async def get_transcript_check(
        self, interview_id: uuid.UUID
    ) -> InterviewTranscriptCheck | None:
        """Return the transcript check for an interview, or None if it has none."""
        result = await self._db.execute(
            select(InterviewTranscriptCheck).where(
                InterviewTranscriptCheck.interview_id == interview_id
            )
        )
        return result.scalar_one_or_none()

    async def create_transcript_check(
        self,
        interview_id: uuid.UUID,
        status: str,
        *,
        match_score: float | None = None,
        server_transcript: str | None = None,
    ) -> InterviewTranscriptCheck:
        """Persist the transcript check for an interview (one per interview)."""
        check = InterviewTranscriptCheck(
            interview_id=interview_id,
            status=status,
            match_score=match_score,
            server_transcript=server_transcript,
        )
        self._db.add(check)
        await self._db.flush()
        return check

    async def create_cost_row(
        self,
        interview_id: uuid.UUID,
        component: str,
        model: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        duration_seconds: float | None = None,
        usage_detail: dict | None = None,
        cost_usd: Decimal | None = None,
    ) -> InterviewCost:
        """Persist one billed-call cost record for an interview."""
        cost_row = InterviewCost(
            interview_id=interview_id,
            component=component,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=duration_seconds,
            usage_detail=usage_detail,
            cost_usd=cost_usd,
        )
        self._db.add(cost_row)
        await self._db.flush()
        return cost_row

    async def get_monthly_cost_summary(self):
        """Total cost_usd + call count per component, for the current calendar month."""
        result = await self._db.execute(
            select(
                InterviewCost.component,
                func.sum(InterviewCost.cost_usd).label("total_cost"),
                func.count(InterviewCost.id).label("total_calls"),
            )
            .where(
                func.date_trunc("month", InterviewCost.created_at)
                == func.date_trunc("month", func.now())
            )
            .group_by(InterviewCost.component)
        )
        return result.all()

    async def get_cost_trend(self, from_date: date | None, to_date: date | None):
        """Per-month, per-component cost/call totals, optionally bounded by
        [from_date, to_date] (inclusive on both ends)."""
        month_col = func.date_trunc("month", InterviewCost.created_at)
        stmt = (
            select(
                month_col.label("month"),
                InterviewCost.component,
                func.sum(InterviewCost.cost_usd).label("total_cost"),
                func.count(InterviewCost.id).label("total_calls"),
            )
            .group_by(month_col, InterviewCost.component)
            .order_by(month_col)
        )
        if from_date:
            stmt = stmt.where(InterviewCost.created_at >= from_date)
        if to_date:
            stmt = stmt.where(InterviewCost.created_at < to_date + timedelta(days=1))
        result = await self._db.execute(stmt)
        return result.all()
