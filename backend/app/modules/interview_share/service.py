"""Business logic for the shared interview results link.

An employer (or Elevare staff running interviews for a client) makes a link for a job. Anyone
holding it can see that job's interview results, read-only, with no login: each candidate's
interview and CV assessment, the recording and the transcript, with the questions the AI
asked made obvious. The link expires, can be revoked, and there is one per job.
"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import PermissionDeniedException, ValidationException
from app.core.ownership import can_manage_job
from app.modules.interview_list.repository import InterviewListRepository
from app.modules.interview_share.models import InterviewShareLink
from app.modules.interview_share.repository import InterviewShareRepository
from app.modules.interview_share.schemas import (
    SharedCandidate,
    SharedResults,
    SharedTurn,
    ShareLinkResponse,
    ShareLinkStatus,
)
from app.modules.interview_share.transcript import parse_turns, questions_asked
from app.modules.interviews.enums import InterviewStatus, TranscriptCheckStatus
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.service import InterviewService
from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.talent_pool.service import resolve_match_display_fields
from app.modules.users.enums import UserRole
from app.modules.users.models import User

# How long a link opens for. It needs no login, so it is short.
SHARE_LINK_DAYS = 3
# The recording's own link works for minutes only: passing it on shares nothing for long.
VIDEO_LINK_SECONDS = 15 * 60
# More candidates than this on one list are not shown (the newest are left off) and the
# page says so; a client list is nowhere near this.
MAX_CANDIDATES = 100

_COMPLETED = (InterviewStatus.UPLOADED.value, InterviewStatus.SCORED.value)

# What the client sees for an interview's state. No interview at all is NOT_INVITED.
_STATUS = {
    InterviewStatus.PENDING.value: "INVITED",
    InterviewStatus.IN_PROGRESS.value: "IN_PROGRESS",
    InterviewStatus.UPLOADED.value: "COMPLETED",
    InterviewStatus.SCORED.value: "COMPLETED",
    InterviewStatus.FAILED.value: "NOT_COMPLETED",
    InterviewStatus.EXPIRED.value: "NOT_COMPLETED",
}
# Completed interviews first (best score first), then the rest in order of progress.
_STATUS_ORDER = {
    "COMPLETED": 0,
    "IN_PROGRESS": 1,
    "INVITED": 2,
    "NOT_COMPLETED": 3,
    "NOT_INVITED": 4,
}

_MISMATCH_NOTE = (
    "This transcript was produced automatically from the recording, so it has no speaker "
    "labels. Please check the video."
)
_UNCHECKED_NOTE = "This transcript could not be checked against the recording."


def _share_error(message: str, code: str, status_code: int) -> ValidationException:
    return ValidationException(message, code=code, status_code=status_code)


class InterviewShareService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = InterviewShareRepository(db)
        self._jobs = JobRepository(db)

    # --- for the people who make the link ---------------------------------------------

    async def _manageable_job(self, user: User, job_id: uuid.UUID) -> Job:
        """The job, if this user may share its results: anyone who can manage the job
        (its owner's organization), and Elevare admins, who run interviews for clients."""
        job = await self._jobs.get_by_id(job_id)
        if not (can_manage_job(user, job) or user.role == UserRole.ADMIN.value):
            raise PermissionDeniedException("You do not have access to this job")
        return job

    @staticmethod
    def _url(token: str) -> str:
        return f"{settings.app_url.rstrip('/')}/shared/interviews/{token}"

    def _response(self, link: InterviewShareLink, now: datetime) -> ShareLinkResponse:
        return ShareLinkResponse(
            url=self._url(link.token),
            created_at=link.created_at,
            expires_at=link.expires_at,
            expired=link.expires_at <= now,
            view_count=link.view_count,
            last_viewed_at=link.last_viewed_at,
        )

    async def get_status(self, user: User, job_id: uuid.UUID) -> ShareLinkStatus:
        await self._manageable_job(user, job_id)
        link = await self._repo.get_active_for_job(job_id)
        if link is None:
            return ShareLinkStatus(link=None)
        return ShareLinkStatus(link=self._response(link, datetime.now(UTC)))

    async def create(self, user: User, job_id: uuid.UUID) -> ShareLinkResponse:
        """Make a new link for the job. Any earlier link stops working: one per job."""
        await self._manageable_job(user, job_id)
        now = datetime.now(UTC)
        # Take turns with anyone else creating a link for this job at the same moment.
        await self._repo.lock_job(job_id)
        await self._repo.revoke_active(job_id, now)
        link = await self._repo.create(
            job_id=job_id,
            token=secrets.token_urlsafe(32),
            created_by=user.id,
            expires_at=now + timedelta(days=SHARE_LINK_DAYS),
        )
        await self._db.commit()
        await self._db.refresh(link)
        return self._response(link, now)

    async def revoke(self, user: User, job_id: uuid.UUID) -> None:
        """Stop the job's link working. Nothing happens if it has none."""
        await self._manageable_job(user, job_id)
        await self._repo.revoke_active(job_id, datetime.now(UTC))
        await self._db.commit()

    # --- for whoever opens the link (no login) ----------------------------------------

    async def get_results(self, token: str) -> SharedResults:
        now = datetime.now(UTC)
        link = await self._repo.get_by_token(token)
        if link is None:
            raise _share_error("This link is not valid.", "SHARE_LINK_NOT_FOUND", 404)
        if link.revoked_at is not None:
            raise _share_error(
                "This link has been replaced or withdrawn. Ask for a new one.",
                "SHARE_LINK_REVOKED",
                410,
            )
        if link.expires_at <= now:
            raise _share_error(
                "This link has expired. Ask for a new one.", "SHARE_LINK_EXPIRED", 410
            )

        await self._repo.record_view(link.id, now)
        results = await self._build_results(link)
        await self._db.commit()
        return results

    async def _build_results(self, link: InterviewShareLink) -> SharedResults:
        job = await self._jobs.get_by_id(link.job_id)
        organization = job.employer.organization if job.employer else None

        entries = await InterviewListRepository(self._db).list_all_for_job(job.id)
        shown = entries[:MAX_CANDIDATES]

        interviews = InterviewRepository(self._db)
        interview_service = InterviewService(self._db)
        candidates = [
            await self._candidate(job, entry.talent_pool_profile, interviews, interview_service)
            for entry in shown
        ]
        candidates.sort(
            key=lambda c: (
                _STATUS_ORDER[c.status],
                -(c.interview_score if c.interview_score is not None else -1),
            )
        )
        # A name the candidate has not shared stays masked until they have interviewed.
        for position, candidate in enumerate(candidates, start=1):
            if not candidate.name:
                candidate.name = f"Candidate {position}"

        return SharedResults(
            job_title=job.title,
            company_name=organization.company_name if organization else None,
            interview_focus=job.interview_brief,
            expires_at=link.expires_at,
            total_candidates=len(entries),
            completed_count=sum(c.status == "COMPLETED" for c in candidates),
            truncated=len(entries) > MAX_CANDIDATES,
            candidates=candidates,
        )

    async def _candidate(
        self,
        job: Job,
        profile,
        interviews: InterviewRepository,
        interview_service: InterviewService,
    ) -> SharedCandidate:
        interview = await interviews.get_by_job_and_profile(job.id, profile.id)
        completed = interview is not None and interview.status in _COMPLETED

        # Completing the interview (on camera) is what identifies a candidate to the
        # employer; until then a name they have not shared stays masked.
        fields = await resolve_match_display_fields(
            self._db, profile, job.employer_id, override_mask=completed
        )
        candidate = SharedCandidate(
            name=fields["name"] or "",
            current_title=fields["current_title"],
            status=_STATUS[interview.status] if interview else "NOT_INVITED",
        )

        if not completed:
            # Not interviewed yet: the CV assessment is still worth showing.
            score, strengths, weaknesses, summary = (
                await interview_service.resolve_cv_assessment(
                    job, profile, interview.application_id if interview else None
                )
            )
            candidate.cv_score = score
            candidate.cv_strengths = strengths
            candidate.cv_weaknesses = weaknesses
            candidate.cv_summary = summary
            return candidate

        # The same detail the employer sees, with a recording link meant to be passed around.
        detail = await interview_service.build_detail(
            job, interview, video_seconds=VIDEO_LINK_SECONDS
        )
        turns = parse_turns(detail.transcript)
        candidate.completed_at = detail.completed_at
        candidate.interview_score = detail.ai_score
        candidate.interview_assessment = detail.ai_rationale
        candidate.cv_score = detail.cv_score
        candidate.cv_summary = detail.cv_fit_summary
        candidate.cv_strengths = detail.cv_strengths
        candidate.cv_weaknesses = detail.cv_weaknesses
        candidate.video_url = detail.video_url
        candidate.questions = questions_asked(turns)
        candidate.turns = [SharedTurn(speaker=t.speaker, text=t.text) for t in turns]
        if not turns:
            candidate.transcript = detail.transcript
        if detail.transcript_check == TranscriptCheckStatus.MISMATCH.value:
            candidate.transcript_note = _MISMATCH_NOTE
        elif detail.transcript_check == TranscriptCheckStatus.UNAVAILABLE.value:
            candidate.transcript_note = _UNCHECKED_NOTE
        return candidate
