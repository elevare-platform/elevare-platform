"""Rescore a job's candidates who have no usable score.

A candidate ends up with no score when their CV could not be read, when scoring failed,
or (in older data) when a failure was saved as a score of 0. This puts them back in the
queue: a CV that could not be read is read again from the stored file and scored when
that finishes, and a readable CV is simply scored again. A candidate with a real score
is never touched.

Cost: every candidate rescored is one or two model calls, so this is limited to paid
plans (like the other scoring endpoints) and to one batch per press.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cv_pipeline.usability import parsed_data_is_usable
from app.core.exceptions import (
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from app.core.ownership import can_manage_job
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.ai.scoring_outcome import SCORING_FAILED, has_real_score, reset_fields
from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.rescore.repository import RescoreRepository
from app.modules.rescore.schemas import RescoreRequest, RescoreResult, RescoreStatus
from app.modules.users.enums import UserRole
from app.modules.users.models import User

logger = logging.getLogger(__name__)

# Candidates started per press. Each is one or two model calls; "Rescore" again to go on.
RESCORE_BATCH = 25
# How many candidates are looked at to find a batch that can be acted on, so a run of
# candidates that cannot be (no stored file) does not block the ones behind them.
SCAN_LIMIT = 200

_IN_FLIGHT = (CVParsingStatus.PENDING.value, CVParsingStatus.PROCESSING.value)


class RescoreService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = RescoreRepository(db)
        self._jobs = JobRepository(db)

    async def _manageable_job(self, user: User, job_id: uuid.UUID) -> Job:
        """The job, if this user may act on it: anyone who can manage it (its owner's
        organization), and Elevare admins, who run jobs for clients."""
        job = await self._jobs.get_by_id(job_id)
        if not (can_manage_job(user, job) or user.role == UserRole.ADMIN.value):
            raise PermissionDeniedException("You do not have access to this job")
        return job

    async def status(self, user: User, job_id: uuid.UUID) -> RescoreStatus:
        await self._manageable_job(user, job_id)
        now = datetime.now(UTC)
        applications = await self._repo.count_applications(job_id, now)
        pipeline = await self._repo.count_pipeline(job_id, now)
        return RescoreStatus(
            applications=applications, pipeline=pipeline, total=applications + pipeline
        )

    async def rescore(
        self, user: User, job_id: uuid.UUID, request: RescoreRequest
    ) -> RescoreResult:
        await self._manageable_job(user, job_id)
        if user.role != UserRole.ADMIN.value:
            from app.modules.billing.service import BillingService

            await BillingService(self._db).assert_professional_or_above(
                user.organization_id
            )

        # Take turns with anyone else pressing Rescore for this job at the same moment:
        # the second one then finds this one's work already done.
        await self._repo.lock_job(job_id)
        now = datetime.now(UTC)

        single = request.application_id or request.talent_pool_profile_id
        if single:
            candidates = [await self._single(job_id, request)]
            waiting_before = len(candidates)
        else:
            applications = await self._repo.applications_needing(job_id, now, SCAN_LIMIT)
            pipeline = await self._repo.pipeline_needing(
                job_id, now, SCAN_LIMIT - len(applications)
            )
            candidates = [("application", a) for a in applications] + [
                ("pipeline", p) for p in pipeline
            ]
            waiting_before = await self._repo.count_applications(
                job_id, now
            ) + await self._repo.count_pipeline(job_id, now)

        plan = await self._plan(candidates)
        await self._db.commit()
        started = self._start(plan)
        # Rows that could not be queued say so, rather than sitting as "waiting".
        if plan["queue_failed"]:
            for _, row in plan["queue_failed"]:
                row.ai_score_failure = SCORING_FAILED
            await self._db.commit()

        done = len(plan["scoring"]) + len(plan["reparse"]) - len(plan["queue_failed"])
        return RescoreResult(
            scoring=started["scoring"],
            reparsing=started["reparsing"],
            in_progress=len(plan["in_progress"]),
            no_stored_file=len(plan["no_file"]),
            remaining=max(waiting_before - done, 0),
        )

    async def _single(self, job_id: uuid.UUID, request: RescoreRequest):
        if request.application_id:
            row = await self._repo.get_application(job_id, request.application_id)
            kind = "application"
        else:
            row = await self._repo.get_pipeline_profile(
                job_id, request.talent_pool_profile_id
            )
            kind = "pipeline"
        if row is None:
            raise NotFoundException("That candidate is not on this job")
        if has_real_score(row):
            raise ValidationException(
                "This candidate already has a score, so there is nothing to rescore"
            )
        return (kind, row)

    async def _plan(self, candidates) -> dict:
        """Decide what to do for each candidate and put the rows back to "not scored
        yet" (this is only staged in the session; the caller commits, then starts the
        work, so a worker never sees a half-done change)."""
        plan = {
            "scoring": [],
            "reparse": [],
            "in_progress": [],
            "no_file": [],
            "queue_failed": [],
            "submissions": {},  # submission id -> submission, to read again
        }
        for kind, row in candidates:
            if len(plan["scoring"]) + len(plan["reparse"]) >= RESCORE_BATCH:
                break
            submission = await (
                self._repo.submission_for_application(row)
                if kind == "application"
                else self._repo.submission_for_profile(row)
            )
            if submission is None:
                plan["no_file"].append((kind, row))
                continue

            already_reparsing = submission.id in plan["submissions"]
            if submission.parse_status in _IN_FLIGHT and not already_reparsing:
                # Still being read: scoring follows by itself when it finishes.
                plan["in_progress"].append((kind, row))
                continue

            readable = (
                not already_reparsing
                and submission.parse_status != CVParsingStatus.FAILED.value
                and submission.parsed_data
                and parsed_data_is_usable(submission.parsed_data)
            )
            if readable:
                self._reset(row)
                plan["scoring"].append((kind, row))
                continue

            if not already_reparsing and not submission.r2_key:
                # Could not be read and there is no stored file to read again.
                plan["no_file"].append((kind, row))
                continue

            if not already_reparsing:
                self._clear_parse(submission)
                plan["submissions"][submission.id] = submission
            self._reset(row)
            plan["reparse"].append((kind, row, submission.id))
        return plan

    @staticmethod
    def _reset(row) -> None:
        for field, value in reset_fields().items():
            setattr(row, field, value)

    @staticmethod
    def _clear_parse(submission: ParsedCVSubmission) -> None:
        """Back to "waiting to be read": the pipeline fills these in again."""
        submission.parse_status = CVParsingStatus.PENDING.value
        submission.parsed_data = None
        submission.deterministic_data = None
        submission.llm_data = None
        submission.flag_reasons = None
        submission.error_message = None

    def _start(self, plan: dict) -> dict:
        """Queue the work, after the changes are saved."""
        from app.modules.ai.tasks import (
            run_full_pipeline_task,
            score_application_task,
            score_talent_pool_profile_task,
        )

        scoring = reparsing = 0
        for kind, row in plan["scoring"]:
            try:
                if kind == "application":
                    score_application_task.delay(str(row.id))
                else:
                    score_talent_pool_profile_task.delay(
                        str(row.id), str(row.sourced_for_job_id)
                    )
                scoring += 1
            except Exception:
                logger.error("rescore: could not queue scoring for %s", row.id, exc_info=True)
                plan["queue_failed"].append((kind, row))

        # Each stored file is read once, however many candidates share it. Scoring
        # follows from the pipeline itself when the read finishes.
        failed_files = set()
        for submission in plan["submissions"].values():
            try:
                run_full_pipeline_task.delay(
                    submission_id=str(submission.id),
                    cache_key=f"cv_parse:{submission.cv_text_hash or submission.id}",
                    r2_key=submission.r2_key,
                )
            except Exception:
                logger.error(
                    "rescore: could not queue reading CV file for submission %s",
                    submission.id,
                    exc_info=True,
                )
                failed_files.add(submission.id)
        for kind, row, submission_id in plan["reparse"]:
            # A file that could not be queued means its candidates are not being read.
            if submission_id in failed_files:
                plan["queue_failed"].append((kind, row))
            else:
                reparsing += 1
        return {"scoring": scoring, "reparsing": reparsing}
