"""Interview service — business logic for AI video interviews."""

import logging
import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from openai import AsyncOpenAI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_pricing import compute_realtime_cost_usd
from app.core.config import settings
from app.core.cost_trend import effective_month_bounds, month_range
from app.core.exceptions import (
    ApplicationNotFound,
    InsufficientCreditsException,
    InterviewNotFound,
    PermissionDeniedException,
    ValidationException,
)
from app.core.ownership import can_manage_job
from app.core.schema_guard import tolerate_missing
from app.core.storage import get_storage_service
from app.modules.ai.interview_scorecard import clean_rating, valid_rating
from app.modules.applications.repository import ApplicationRepository
from app.modules.candidates.repository import CandidateRepository
from app.modules.credits.service import CreditsService
from app.modules.interview_list.repository import InterviewListRepository
from app.modules.interviews.enums import (
    ENDED_STATUSES,
    PANEL_DECISION_LABELS,
    RESCORE_DONE,
    RESCORE_FAILED,
    RESCORE_PENDING,
    RESCORE_STALE_AFTER,
    InterviewCostComponent,
    InterviewStatus,
    PanelDecision,
    TranscriptCheckStatus,
    follow_up_mode_of,
)
from app.modules.interviews.follow_up import load_follow_up_mode
from app.modules.interviews.models import (
    Interview,
    InterviewPanelDecision,
    InterviewRescore,
    InterviewScoreReview,
    InterviewTurn,
    InterviewWeightedScore,
    JobInterviewQuestion,
    JobScoreVisibility,
)
from app.modules.interviews.recording_merge import attempt_of_key, final_key, part_key
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.schema import (
    InterviewDetailResponse,
    InterviewPublicInfoResponse,
    InterviewSessionResponse,
    InterviewUploadUrlResponse,
    RealtimeUsageDetail,
    RecordingClip,
    StrictRecordingPartResponse,
    UploadFailureRequest,
)
from app.modules.interviews.score_review import (
    MAX_SCORE,
    MIN_SCORE,
    apply_review,
)
from app.modules.interviews.score_visibility import (
    hide_numbers,
    hide_scores,
    strip_gaps,
)
from app.modules.interviews.scorecard import build_scorecard, system_evidence
from app.modules.interviews.scoring_access import assert_can_score_interviews
from app.modules.interviews.strict import StrictInterviewService
from app.modules.interviews.tasks import (
    merge_interview_recording_task,
    rescore_interview_task,
    send_ai_interview_invite_email,
    send_interview_restart_request_email,
    transcribe_and_score_interview_task,
)
from app.modules.jobs.models import Job
from app.modules.talent_pool.repository import TalentPoolRepository
from app.modules.users.enums import UserRole
from app.modules.users.models import User

logger = logging.getLogger(__name__)

# An interview that has been "being scored" for longer than this is stuck (the
# worker died mid-run), so scoring may be requested again.
_SCORING_STUCK_AFTER = timedelta(minutes=15)

_UPLOAD_URL_EXPIRES_SECONDS = 60 * 30
_ENDED_EARLY_MESSAGE = (
    "This interview ended early. Reinstate it to let the candidate carry on, "
    "instead of sending the link again."
)
_VIDEO_CONTENT_TYPE = "video/webm"
_INVITE_TOKEN_EXPIRY_DAYS = 14

# The "interviewer" line of the candidate assessment record (docs/16_COLTON_BRIEF.md, Section 7).
RECORD_INTERVIEWER = "Elevare structured interview"


def minutes_spent(
    started_at: datetime | None, ended_at: datetime | None, last_answered_at: datetime | None
) -> int | None:
    """The minutes the candidate spent in the interview, for the assessment record: from its start to
    their last answer, or to the moment it was ended or stopped if that came later. Not to the end of
    the video upload (``completed_at``), which can be hours later on a slow connection or after a
    failed upload, and made the record show more minutes than the interview can last."""
    if started_at is None:
        return None
    finish = max((moment for moment in (ended_at, last_answered_at) if moment is not None), default=None)
    if finish is None:
        return None
    return max(0, round((finish - started_at).total_seconds() / 60))


# A panel decision can be recorded once the interview has finished, however it ended.
PANEL_DECISION_STATUSES = (
    InterviewStatus.UPLOADED.value,
    InterviewStatus.SCORED.value,
    *ENDED_STATUSES,
)
# The shortest rationale that says something (a sentence or two).
MIN_RATIONALE_CHARS = 10


def _panel_decision_out(row: InterviewPanelDecision) -> dict:
    """A recorded decision as the API shows it."""
    return {
        "decision": row.decision,
        "label": PANEL_DECISION_LABELS.get(row.decision, row.decision),
        "rationale": row.rationale,
        "decided_by_name": row.decided_by_name,
        "decided_at": row.decided_at,
    }

_BASE_INTERVIEWER_INSTRUCTIONS = (
    "You are conducting a live, spoken screening interview on behalf of an "
    "employer. Ask an opening question based on the brief below, listen to "
    "the candidate's spoken answer, and ask real follow-up questions based "
    "on what they actually say, the way a human interviewer would. Keep "
    "the conversation focused and professional. Speak naturally and "
    "conversationally, the way a real interviewer talks, not like a script "
    "being read aloud. Do not reveal the brief itself to the candidate."
)


END_INTERVIEW_TOOL_NAME = "end_interview"

# Lets the interviewer finish the session itself once the brief is covered. The
# browser watches for this call, waits for the goodbye to finish playing, then
# ends the interview, so the candidate is not left waiting for the timer.
_END_INTERVIEW_TOOL = {
    "type": "function",
    "name": END_INTERVIEW_TOOL_NAME,
    "description": (
        "Ends the interview. Call it only after the topics in the brief have "
        "been covered and you have thanked the candidate and said goodbye out "
        "loud, in that same turn. Never call it before saying goodbye."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def _build_instructions(
    interview_brief: str,
    max_duration_minutes: int,
    can_end_interview: bool = True,
) -> str:
    """Compose the realtime session's system instructions from the job's interview brief."""
    length = (
        f"The interview can last up to {max_duration_minutes} minutes, but that "
        "is a ceiling, not a target. Do not try to fill the time. Most "
        "interviews should finish well before it.\n"
        "- Work through the topics in the brief once, in a natural order.\n"
        "- Ask a follow-up question only when an answer is vague, gives no "
        "concrete example, or leaves the question unanswered. Ask at most two "
        "follow-ups on any one topic. Once you have a reasonably clear picture "
        "of the candidate on a topic, move on, even if you could ask more.\n"
        "- Never invent extra questions just to use up the time.\n"
        "- If a candidate goes into long detail on one topic, politely "
        "acknowledge what they have shared and move to the next question, so "
        "every topic in the brief gets covered."
    )
    closing = (
        "When every topic in the brief has been covered well enough, close the "
        "interview. Thank the candidate, tell them the employer will review the "
        "interview and be in touch, and say goodbye. Keep the closing to two or "
        "three sentences and ask no more questions after it. If you are told "
        "that time is nearly up, skip any topics you have not reached and close "
        "in the same way right away."
    )
    if can_end_interview:
        closing += (
            f" Right after you have said goodbye, in that same turn, call the "
            f"{END_INTERVIEW_TOOL_NAME} function. Never call it before saying "
            "goodbye, and never in the first minutes of the interview."
        )
    else:
        closing += " After saying goodbye, stop speaking and wait."
    return (
        f"{_BASE_INTERVIEWER_INSTRUCTIONS}\n\nHOW LONG THE INTERVIEW SHOULD LAST\n"
        f"{length}\n\nHOW TO CLOSE\n{closing}"
        f"\n\nInterview brief:\n{interview_brief}"
    )


def resolve_candidate_email(profile) -> str | None:
    """Resolve a talent pool profile's contact email.

    Self-registered  -> candidate_profile.user.email (verified account, always wins)
    Employer-entered -> override_email (manual correction, beats an auto-parsed guess)
    Sourced-only     -> parsed_submission.parsed_data.email (last resort)
    """
    if profile.candidate_profile and profile.candidate_profile.user:
        return profile.candidate_profile.user.email
    if profile.override_email:
        return profile.override_email
    if profile.parsed_submission and profile.parsed_submission.parsed_data:
        return profile.parsed_submission.parsed_data.get("email")
    return None


def resolve_candidate_name(profile) -> str | None:
    """Resolve a talent pool profile's display name, same fallback chain as
    resolve_candidate_email."""
    if profile.candidate_profile and profile.candidate_profile.user:
        user = profile.candidate_profile.user
        return f"{user.first_name} {user.last_name}".strip() or None
    if profile.override_name:
        return profile.override_name
    if profile.parsed_submission and profile.parsed_submission.parsed_data:
        return profile.parsed_submission.parsed_data.get("full_name")
    return None


class InterviewService:
    """Orchestrates business logic for the AI video interview lifecycle."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the service with a database session and its repositories."""
        self._db = db
        self._repo = InterviewRepository(db)
        self._application_repo = ApplicationRepository(db)
        self._candidate_repo = CandidateRepository(db)
        self._interview_list_repo = InterviewListRepository(db)
        self._talent_pool_repo = TalentPoolRepository(db)
        self._client: AsyncOpenAI | None = None

    async def close(self) -> None:
        """Close the underlying OpenAI HTTP client, if one was created."""
        if self._client is not None:
            await self._client.close()

    def _strict(self) -> StrictInterviewService:
        """The strict interview's own logic (tests replace this to avoid real API calls)."""
        return StrictInterviewService(self._db, self._repo)

    def _get_client(self) -> AsyncOpenAI:
        """Lazily construct the OpenAI client so most code paths (which never
        touch the realtime API) don't require OPENAI_API_KEY to be set."""
        if self._client is None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        return self._client

    # ------------------------------------------------------------------
    # Invite — called by InterviewListService when an employer adds a
    # candidate to a job's interview list. Creates (or reuses) the
    # Interview row and a fresh token, and returns everything needed to
    # email the candidate a no-login link.
    # ------------------------------------------------------------------

    async def _has_interview(self, job: Job) -> bool:
        """Whether the job has an interview to invite people to: a written brief or, for the
        strict interview, saved questions (there the brief is optional: the questions are the
        interview)."""
        if job.interview_brief:
            return True
        if settings.interview_style != "strict":
            return False
        found = await self._db.execute(
            select(JobInterviewQuestion.id).where(JobInterviewQuestion.job_id == job.id).limit(1)
        )
        return found.first() is not None

    async def create_invite(
        self, job: Job, talent_pool_profile_id: uuid.UUID
    ) -> tuple[Interview, str] | None:
        """Get-or-create the Interview row for this job+candidate and (re)issue a token.

        Returns (interview, interview_url) or None if the job has no
        interview configured (no brief and, for the strict interview, no
        questions) — being on the interview list only triggers an
        interview invite for jobs that actually have the feature turned on.
        """
        if not await self._has_interview(job):
            return None

        interview = await self._repo.get_by_job_and_profile(
            job.id, talent_pool_profile_id
        )
        if interview is not None:
            # Take this interview's lock before deciding anything. The hourly sweep
            # that refunds expired invites takes the same lock, so a resend and a
            # refund always take turns: without it the sweep could refund the
            # credits just as a resend hands out a live link, a free interview.
            await self._repo.lock_status(interview.id)
            await self._db.refresh(interview)
        if interview is None:
            # The style is decided here, once, for this interview. A strict interview
            # needs the job's questions, so that is checked before anything is charged.
            strict = settings.interview_style == "strict"
            if strict:
                await self._strict().require_questions(job.id)
            # Charge before anything is saved: the id is decided first, so when
            # the credits are short nothing exists to clean up, and the charge and
            # the interview are committed together below or not at all.
            new_interview_id = uuid.uuid4()
            await self._charge_for_invite(job, new_interview_id)
            application_id = await self._find_matching_application_id(
                job.id, talent_pool_profile_id
            )
            interview = await self._repo.create(
                job_id=job.id,
                talent_pool_profile_id=talent_pool_profile_id,
                application_id=application_id,
                interview_id=new_interview_id,
            )
            if strict:
                await self._strict().create_run(interview.id)
        elif interview.status in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            # Already completed — nothing new to invite them to.
            return None
        elif interview.status in ENDED_STATUSES:
            # Sending the link again would only show the candidate that it has ended.
            raise ValidationException(_ENDED_EARLY_MESSAGE, code="INTERVIEW_ENDED_EARLY")
        else:
            # A resend or a re-invite. Free while the interview is still paid; an
            # interview whose credits were refunded (the invite expired unused) is
            # charged again. Short on credits: this raises before anything below
            # changes the existing interview.
            await self._charge_for_invite(job, interview.id)

        token = secrets.token_urlsafe(32)
        update_data: dict = {
            "token": token,
            "token_expires_at": datetime.now(UTC)
            + timedelta(days=_INVITE_TOKEN_EXPIRY_DAYS),
            # An explicit (re)invite is a deliberate employer action, not
            # the candidate's own reload — safe to reset the restart lock
            # here since we've already ruled out UPLOADED/SCORED above.
            # This is the manual override the _start_session error message
            # points candidates/recruiters to.
            "session_start_count": 0,
            "reset_requested_at": None,
        }
        if interview.status == InterviewStatus.IN_PROGRESS.value:
            update_data["status"] = InterviewStatus.PENDING.value
        interview = await self._repo.update(interview.id, update_data)
        await self._db.commit()

        interview_url = f"{settings.app_url}/interview/{token}"
        return interview, interview_url

    async def _find_matching_application_id(
        self, job_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> uuid.UUID | None:
        """Best-effort link to a real Application, for the logged-in candidate view only."""
        profile = await self._talent_pool_repo.get_by_id_joined_with_other_data(
            talent_pool_profile_id
        )
        if profile is None or profile.candidate_profile_id is None:
            return None
        application = await self._application_repo.has_applied(
            profile.candidate_profile.user_id, job_id
        )
        return application.id if application else None

    # ------------------------------------------------------------------
    # Logged-in candidate path — resolves via application_id + auth
    # ------------------------------------------------------------------

    async def create_session(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> InterviewSessionResponse:
        """Mint a Realtime API session for a logged-in candidate's interview."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._start_session(interview)

    async def request_reset(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> dict:
        """Logged-in candidate asks the employer to reset their restart lock."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._request_reset(interview)

    async def generate_upload_url(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> InterviewUploadUrlResponse:
        """Return a presigned upload URL for a logged-in candidate's recording."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._generate_upload_url(interview)

    async def complete_upload(
        self,
        application_id: uuid.UUID,
        candidate_id: uuid.UUID,
        transcript: str | None = None,
        realtime_usage: RealtimeUsageDetail | None = None,
    ):
        """Mark a logged-in candidate's recording as uploaded."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._complete_upload(
            interview, transcript=transcript, realtime_usage=realtime_usage
        )

    async def get_for_application(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ):
        """Return the interview for an application, enforcing candidate ownership."""
        return await self._resolve_owned_interview(application_id, candidate_id)

    async def _resolve_owned_interview(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> Interview:
        """Resolve the Interview for a logged-in candidate's application, checking ownership + invite."""
        application = await self._application_repo.get_by_id(application_id)
        if application is None:
            raise ApplicationNotFound()
        if application.candidate_id != candidate_id:
            raise PermissionDeniedException(
                "You do not have access to this application"
            )
        if not await self._has_interview(application.job):
            raise ValidationException(
                "This job does not have a video interview configured"
            )

        candidate_profile = await self._candidate_repo.get_by_user_id(candidate_id)
        if candidate_profile is None:
            raise PermissionDeniedException("Candidate profile not found")
        talent_pool_profile = await self._talent_pool_repo.get_by_candidate_profile_id(
            candidate_profile.id
        )
        if talent_pool_profile is None or not await self._interview_list_repo.is_candidate_invited(
            application.job_id, candidate_profile.id
        ):
            raise PermissionDeniedException(
                "The employer has not invited you to an AI video interview for "
                "this application yet"
            )

        interview = await self._repo.get_by_job_and_profile(
            application.job_id, talent_pool_profile.id
        )
        if interview is None:
            raise InterviewNotFound()
        return interview

    # ------------------------------------------------------------------
    # Token path — no login required, for an emailed invite link
    # ------------------------------------------------------------------

    async def get_public_info(self, token: str) -> InterviewPublicInfoResponse:
        """Return job/company context for the consent screen, before starting."""
        interview = await self._resolve_interview_by_token(token)
        job = interview.job
        employer_profile = getattr(getattr(job, "employer", None), "organization", None)
        run = await self._strict().get_run(interview.id)
        strict = run is not None
        return InterviewPublicInfoResponse(
            job_title=job.title,
            company_name=employer_profile.company_name if employer_profile else None,
            status=interview.status,
            max_duration_minutes=settings.interview_max_duration_minutes,
            session_start_count=interview.session_start_count,
            style="strict" if strict else "live",
            started=bool(run and run.started_at is not None),
            follow_up_mode=await self.follow_up_mode_for(interview) if strict else "STANDARD",
        )

    async def create_session_by_token(self, token: str) -> InterviewSessionResponse:
        """Mint a Realtime API session from an emailed invite link, no login required."""
        interview = await self._resolve_interview_by_token(token)
        return await self._start_session(interview)

    async def request_reset_by_token(self, token: str) -> dict:
        """No-login candidate asks the employer to reset their restart lock."""
        interview = await self._resolve_interview_by_token(token)
        return await self._request_reset(interview)

    async def generate_upload_url_by_token(
        self, token: str
    ) -> InterviewUploadUrlResponse:
        """Return a presigned upload URL from an emailed invite link."""
        interview = await self._resolve_interview_by_token(token)
        return await self._generate_upload_url(interview)

    async def complete_upload_by_token(
        self,
        token: str,
        transcript: str | None = None,
        realtime_usage: RealtimeUsageDetail | None = None,
    ):
        """Mark the recording uploaded, resolved from an emailed invite link."""
        interview = await self._resolve_interview_by_token(token)
        return await self._complete_upload(
            interview, transcript=transcript, realtime_usage=realtime_usage
        )

    # ------------------------------------------------------------------
    # The strict interview: start or resume it, and answer a question. Both ways in (the
    # emailed link and the logged-in candidate) end in the same two calls.
    # ------------------------------------------------------------------

    async def style_of(self, interview: Interview) -> str:
        """"strict" or "live": which interview this one is, fixed when it was invited."""
        return "strict" if await self._strict().is_strict(interview.id) else "live"

    async def is_started(self, interview: Interview) -> bool:
        """Whether this is a strict interview that has been started."""
        run = await self._strict().get_run(interview.id)
        return bool(run and run.started_at is not None)

    async def follow_up_mode_for(self, interview: Interview) -> str:
        """What the AI may do after an answer in this interview (NONE, STANDARD, PROBES_ONLY), so
        the rules the candidate reads say the same. Once the interview has started it is the mode
        copied at the start; before that, the job's mode as it is now."""
        run = await self._strict().get_run(interview.id)
        if run is not None and run.started_at is not None:
            return follow_up_mode_of(run.follow_up_mode).value
        return (await load_follow_up_mode(self._db, interview.job_id)).value

    async def _record_strict_event(
        self, interview: Interview, event_type: str, cause: str | None, key: str | None
    ) -> dict:
        self._assert_interviews_enabled()
        return await self._strict().record_event(
            interview, event_type=event_type, cause=cause, key=key
        )

    def _log_upload_failure(self, interview: Interview, body: UploadFailureRequest) -> None:
        """One line a person can search for (``interview_upload_failure``) when a candidate's
        recording does not arrive. Nothing is stored and the interview is not touched."""
        logger.warning(
            "interview_upload_failure interview=%s job=%s stage=%s reason=%s http_status=%s "
            "attempt=%s size_bytes=%s status=%s",
            interview.id,
            interview.job_id,
            body.stage,
            body.reason,
            body.http_status,
            body.attempt,
            body.size_bytes,
            interview.status,
        )

    async def report_upload_failure_by_token(self, token: str, body: UploadFailureRequest) -> None:
        """The candidate's screen reports that sending the recording failed (emailed link)."""
        interview = await self._resolve_interview_by_token(token)
        self._log_upload_failure(interview, body)

    async def report_upload_failure(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID, body: UploadFailureRequest
    ) -> None:
        """The same, from a logged-in candidate."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        self._log_upload_failure(interview, body)

    async def strict_event_by_token(
        self, token: str, event_type: str, cause: str | None, key: str | None
    ) -> dict:
        """The candidate's screen reports a leave, a return, a key press or a heartbeat."""
        interview = await self._resolve_interview_by_token(token)
        return await self._record_strict_event(interview, event_type, cause, key)

    async def strict_event(
        self,
        application_id: uuid.UUID,
        candidate_id: uuid.UUID,
        event_type: str,
        cause: str | None,
        key: str | None,
    ) -> dict:
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._record_strict_event(interview, event_type, cause, key)

    async def stop_strict_by_token(self, token: str) -> dict:
        """The candidate pressed "I need to stop" and confirmed."""
        interview = await self._resolve_interview_by_token(token)
        self._assert_interviews_enabled()
        return await self._strict().stop(interview)

    async def stop_strict(self, application_id: uuid.UUID, candidate_id: uuid.UUID) -> dict:
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        self._assert_interviews_enabled()
        return await self._strict().stop(interview)

    async def reinstate(
        self, user: User, job_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> dict:
        """The employer who owns the job lets a candidate carry on with an interview that
        ended early (by the system, or because the candidate stopped it).

        Organization-level ownership (decision D2): anyone in the company that owns the job;
        an Elevare admin gets nothing extra from that rule. Nothing is charged. The candidate
        is sent the same link again, valid for 14 more days.
        """
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None:
            raise InterviewNotFound()
        updated = await self._strict().reinstate(interview)

        sent = await self._email_strict_link(job, talent_pool_profile_id, updated.token)
        return {
            "status": updated.status,
            "interview_url": f"{settings.app_url}/interview/{updated.token}",
            "email_sent": sent,
        }

    async def _email_strict_link(
        self, job: Job, talent_pool_profile_id: uuid.UUID, token: str | None
    ) -> bool:
        """Email the candidate their strict interview link again. False when there is no address
        on file or no link to send."""
        profile = await self._talent_pool_repo.get_by_id_joined_with_other_data(
            talent_pool_profile_id
        )
        candidate_email = resolve_candidate_email(profile) if profile else None
        if not candidate_email or not token:
            return False
        organization = job.employer.organization if job.employer else None
        company_name = (
            organization.company_name if organization and organization.company_name else None
        )
        from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME

        send_ai_interview_invite_email.delay(
            candidate_email=candidate_email,
            interview_url=f"{settings.app_url}/interview/{token}",
            job_title=job.title,
            company_name=company_name or PLATFORM_COMPANY_NAME,
            strict=True,
        )
        return True

    async def _delete_recordings(self, keys: list[str]) -> None:
        """Remove the stored files of an attempt that was started over. Best effort and after the
        reset is saved: a file that cannot be removed is only left behind (the retention sweep
        no longer knows it), and never undoes the restart."""
        storage = get_storage_service()
        for key in keys:
            try:
                await storage.delete_file(key)
            except Exception:
                logger.warning("start_over: could not delete %s", key, exc_info=True)

    async def recover_failed(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        *,
        start_over: bool,
    ) -> dict:
        """The employer recovers a strict interview that failed before it was finished (the
        candidate answered, but the recording never arrived and the stale sweep gave up).

        Three outcomes, by what is true now:
        * ``completed``: the recording turns out to be in storage after all (only the
          confirmation was lost), so the interview is completed and scored, and the candidate
          does nothing.
        * ``reopened``: the candidate is sent the link again and finishes where they stopped,
          sending the recording their browser kept (``start_over`` false).
        * ``started_over``: a fresh interview with new questions and a new clock, for when the
          recording is gone (``start_over`` true). The unfinished attempt is discarded, its
          recording files included. Also allowed for an interview that ended early or was
          stopped, when the employer wants a retake rather than a reinstatement. Also allowed for
          an interview still IN_PROGRESS whose candidate has gone quiet for ten minutes (a frozen
          laptop, a dead connection): it gets a NEW link and the old one stops working; sooner
          than that it is refused (``INTERVIEW_CANDIDATE_ACTIVE``). Free: the first attempt is
          still paid.

        Organization-level ownership (decision D2). Free while the interview is still paid; one
        whose credits were refunded is charged again, as a resend is. Safe to press twice: the
        second call finds an interview that is no longer FAILED and is refused.
        """
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None or not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None:
            raise InterviewNotFound()
        self._assert_interviews_enabled()
        strict = self._strict()
        if not await strict.is_strict(interview.id):
            raise ValidationException(
                "Only a strict interview can be recovered this way.",
                code="INTERVIEW_NOT_RECOVERABLE",
            )

        if not start_over and interview.status in ENDED_STATUSES:
            raise ValidationException(
                "This interview ended early. Reinstate it so the candidate carries on, or start it over.",
                code="INTERVIEW_NOT_RECOVERABLE",
            )

        # A COMPLETED interview (scored, or whose scoring failed) can be taken again, only by
        # starting it over: the first result is replaced. Looked at under the row lock, so a
        # double click cannot take the credits twice (the second finds it already restarted).
        retake = False
        await self._repo.lock_status(interview.id)
        await self._db.refresh(interview)
        finished = interview.status == InterviewStatus.SCORED.value or (
            interview.status == InterviewStatus.FAILED.value and interview.completed_at is not None
        )
        if finished and not start_over:
            raise ValidationException(
                "This interview is finished. To let the candidate take it again, start it over.",
                code="INTERVIEW_NOT_RECOVERABLE",
            )
        if start_over and interview.status == InterviewStatus.UPLOADED.value:
            raise ValidationException(
                "This interview is still being scored. Please try again in a few minutes.",
                code="INTERVIEW_PROCESSING",
            )
        if start_over and finished:
            retake = True

        if not start_over and interview.r2_key:
            # The recording may have reached storage with only the confirmation lost.
            try:
                size = await get_storage_service().get_object_size(interview.r2_key)
            except Exception:
                logger.warning(
                    "recover_failed: could not ask storage about %s", interview.r2_key, exc_info=True
                )
                size = 0
            if size:
                await self._repo.lock_status(interview.id)
                await self._db.refresh(interview)
                if (
                    interview.status != InterviewStatus.FAILED.value
                    or interview.completed_at is not None
                ):
                    raise ValidationException(
                        "Only an interview that was started but never finished can be recovered.",
                        code="INTERVIEW_NOT_RECOVERABLE",
                    )
                await self._charge_for_invite(job, interview.id)
                await self._repo.update(
                    interview.id, {"status": InterviewStatus.IN_PROGRESS.value}
                )
                done = await self._complete_upload(interview)
                return {
                    "outcome": "completed",
                    "status": done.status,
                    "interview_url": None,
                    "email_sent": False,
                }

        # A retake is a new interview with its own cost: it takes the credits again even though
        # the first attempt is paid. Every other recovery is free while the interview is paid.
        await self._charge_for_invite(job, interview.id, again=retake)
        if start_over:
            # The files of the attempt being discarded, read before the run is reset.
            run = await strict.get_run(interview.id)
            if retake:
                logger.info(
                    "interview retake: interview=%s by user=%s discards score=%s",
                    interview.id,
                    user.id,
                    interview.ai_score,
                )
            old_keys = [interview.r2_key, *((run.previous_recordings or []) if run else [])]
            old_keys += [part_key(interview.id, n) for n in range(1, (run.recording_parts if run else 0) + 1)]
            updated = await strict.start_over(interview)
            await self._delete_recordings([key for key in old_keys if key])
            outcome = "started_over"
        else:
            updated = await strict.reopen_failed(interview)
            outcome = "reopened"
        sent = await self._email_strict_link(job, talent_pool_profile_id, updated.token)
        return {
            "outcome": outcome,
            "status": updated.status,
            "interview_url": f"{settings.app_url}/interview/{updated.token}",
            "email_sent": sent,
        }

    async def _start_strict(
        self, interview: Interview, accepted: bool, rules_version: str | None
    ) -> dict:
        self._assert_interviews_enabled()
        return await self._strict().start(
            interview, accepted=accepted, rules_version=rules_version
        )

    async def _answer_strict(
        self,
        interview: Interview,
        turn_id: uuid.UUID,
        audio: bytes,
        content_type: str | None,
    ) -> dict:
        self._assert_interviews_enabled()
        return await self._strict().answer(
            interview, turn_id=turn_id, audio=audio, content_type=content_type
        )

    async def _recording_part_url(self, interview: Interview) -> StrictRecordingPartResponse:
        self._assert_interviews_enabled()
        part = await self._strict().reserve_recording_part(interview)
        upload_url = await get_storage_service().generate_presigned_upload_url(
            part_key(interview.id, part), _VIDEO_CONTENT_TYPE, _UPLOAD_URL_EXPIRES_SECONDS
        )
        return StrictRecordingPartResponse(
            upload_url=upload_url, expires_in_seconds=_UPLOAD_URL_EXPIRES_SECONDS, part=part
        )

    async def recording_part_url_by_token(self, token: str) -> StrictRecordingPartResponse:
        """An upload URL for an earlier recording kept across a reload, from an emailed link."""
        return await self._recording_part_url(await self._resolve_interview_by_token(token))

    async def recording_part_url(
        self, application_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> StrictRecordingPartResponse:
        """The same, for a logged-in candidate."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._recording_part_url(interview)

    async def start_strict_by_token(
        self, token: str, accepted: bool, rules_version: str | None
    ) -> dict:
        """Start or resume the strict interview from an emailed invite link."""
        interview = await self._resolve_interview_by_token(token)
        return await self._start_strict(interview, accepted, rules_version)

    async def answer_strict_by_token(
        self, token: str, turn_id: uuid.UUID, audio: bytes, content_type: str | None
    ) -> dict:
        """Save one spoken answer of the strict interview, from an emailed invite link."""
        interview = await self._resolve_interview_by_token(token)
        return await self._answer_strict(interview, turn_id, audio, content_type)

    async def start_strict(
        self,
        application_id: uuid.UUID,
        candidate_id: uuid.UUID,
        accepted: bool,
        rules_version: str | None,
    ) -> dict:
        """Start or resume the strict interview for a logged-in candidate."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._start_strict(interview, accepted, rules_version)

    async def answer_strict(
        self,
        application_id: uuid.UUID,
        candidate_id: uuid.UUID,
        turn_id: uuid.UUID,
        audio: bytes,
        content_type: str | None,
    ) -> dict:
        """Save one spoken answer of the strict interview for a logged-in candidate."""
        interview = await self._resolve_owned_interview(application_id, candidate_id)
        return await self._answer_strict(interview, turn_id, audio, content_type)

    async def _resolve_interview_by_token(self, token: str) -> Interview:
        interview = await self._repo.get_by_token(token)
        if interview is None:
            raise InterviewNotFound()
        if (
            interview.token_expires_at is not None
            and interview.token_expires_at < datetime.now(UTC)
        ):
            raise ValidationException("This interview invite link has expired")
        # Being on the job's interview list is what grants access (see the
        # Interview model's own docstring) — the logged-in path already
        # checks this at every request via is_candidate_invited. The token
        # path must too: an employer removing a candidate from the list
        # should revoke access immediately, not just for the ~14 days
        # until the token happens to expire on its own.
        if not await self._interview_list_repo.is_profile_invited(
            interview.job_id, interview.talent_pool_profile_id
        ):
            raise PermissionDeniedException(
                "You are no longer on this job's interview list"
            )
        return interview

    # ------------------------------------------------------------------
    # Shared session/upload/complete logic
    # ------------------------------------------------------------------

    async def _start_session(self, interview: Interview) -> InterviewSessionResponse:
        self._assert_interviews_enabled()

        if interview.status in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            raise ValidationException("This interview has already been completed")

        # A strict interview has no live voice session to mint.
        if await self._strict().is_strict(interview.id):
            raise ValidationException(
                "This is a strict interview, not a live one.", code="INTERVIEW_WRONG_STYLE"
            )

        # Each call mints a brand-new Realtime conversation — reloading
        # mid-interview would otherwise let a candidate hear the AI's
        # opening question, restart, and answer with a running start. One
        # restart is tolerated (a genuine crash/dropped connection); a
        # second is blocked.
        if interview.session_start_count >= 2:
            raise ValidationException(
                "This interview has already been started twice. "
                "Please ask your recruiter to reset it.",
                code="INTERVIEW_RESTART_LOCKED",
            )

        job = interview.job
        max_duration_minutes = settings.interview_max_duration_minutes
        can_end_early = settings.interview_ai_can_end_early
        session_config: dict = {
            "type": "realtime",
            "model": settings.realtime_model,
            "instructions": _build_instructions(
                job.interview_brief, max_duration_minutes, can_end_early
            ),
            "audio": {
                "input": {
                    "turn_detection": {
                        "type": "semantic_vad",
                        "eagerness": "low",
                        "create_response": True,
                        "interrupt_response": True,
                    },
                    "noise_reduction": {"type": "far_field"},
                    # Transcribes the candidate's own speech server-side
                    # so the frontend can capture a diarized transcript
                    # from Realtime events directly, instead of relying
                    # on Whisper against the (one-sided) recording.
                    "transcription": {"model": settings.transcription_model},
                },
            },
        }
        if can_end_early:
            session_config["tools"] = [_END_INTERVIEW_TOOL]
            session_config["tool_choice"] = "auto"

        secret = await self._get_client().realtime.client_secrets.create(
            expires_after={
                "anchor": "created_at",
                "seconds": min(max_duration_minutes * 60, 7200),
            },
            session=session_config,
        )

        update_data: dict = {
            "status": InterviewStatus.IN_PROGRESS.value,
            "session_start_count": interview.session_start_count + 1,
        }
        if interview.started_at is None:
            update_data["started_at"] = datetime.now(UTC)
        interview = await self._repo.update(interview.id, update_data)
        await self._db.commit()

        return InterviewSessionResponse(
            interview_id=interview.id,
            client_secret=secret.value,
            expires_at=datetime.fromtimestamp(secret.expires_at, tz=UTC),
            realtime_model=settings.realtime_model,
            max_duration_minutes=max_duration_minutes,
        )

    async def _request_reset(self, interview: Interview) -> dict:
        """Notify the employer that a candidate is locked out of their
        restart-locked interview and needs it reset — the dedicated action
        the _start_session error message points candidates to, instead of
        leaving them with only a "try again" button that would just fail
        the same way again.
        """
        if interview.session_start_count < 2:
            raise ValidationException(
                "This interview isn't currently locked, so there's nothing to reset."
            )
        if interview.reset_requested_at is not None:
            # Already notified once and the employer hasn't resent yet
            # (that's what clears reset_requested_at) — no-op instead of
            # spamming the employer on every repeat click.
            return {"sent": False, "already_requested": True}

        from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME
        from app.modules.notifications.repository import NotificationRepository

        job = interview.job
        employer = job.employer
        organization = employer.organization if employer else None
        company_name = (
            organization.company_name
            if organization and organization.company_name
            else PLATFORM_COMPANY_NAME
        )
        candidate_name = (
            resolve_candidate_name(interview.talent_pool_profile) or "A candidate"
        )

        if employer and employer.email:
            manage_url = (
                f"{settings.app_url}/employer/jobs/{job.id}/applicants"
                "?tab=interview-list"
            )
            send_interview_restart_request_email.delay(
                employer_email=employer.email,
                candidate_name=candidate_name,
                job_title=job.title,
                company_name=company_name,
                manage_url=manage_url,
            )
            await NotificationRepository(self._db).create(
                recipient_id=employer.id,
                type="AI_INTERVIEW_RESET_REQUEST",
                title=f"{candidate_name} needs their interview reset",
                body=(
                    f"{candidate_name} was locked out of their interview for "
                    f"{job.title} after restarting it twice, and is asking you "
                    "to resend their invite to reset it."
                ),
                entity_type="JOB",
                entity_id=job.id,
                # Lets the notification page resend the invite directly,
                # without the employer having to navigate to the interview
                # list and find the right row themselves.
                context={
                    "job_id": str(job.id),
                    "talent_pool_profile_id": str(interview.talent_pool_profile_id),
                    "candidate_name": candidate_name,
                },
            )

        await self._repo.update(interview.id, {"reset_requested_at": datetime.now(UTC)})
        await self._db.commit()
        return {"sent": True, "already_requested": False}

    async def _generate_upload_url(
        self, interview: Interview
    ) -> InterviewUploadUrlResponse:
        # An interview that ended early still sends the recording it has, as evidence.
        if interview.status not in (
            InterviewStatus.PENDING.value,
            InterviewStatus.IN_PROGRESS.value,
            *ENDED_STATUSES,
        ):
            raise ValidationException("This interview has already been uploaded")

        # A reinstated strict interview records again; each attempt has its own file, so the
        # earlier recording is never overwritten.
        run = await self._strict().get_run(interview.id)
        key = final_key(interview.id, run.attempt if run else 1)
        storage = get_storage_service()
        upload_url = await storage.generate_presigned_upload_url(
            key, _VIDEO_CONTENT_TYPE, _UPLOAD_URL_EXPIRES_SECONDS
        )
        await self._repo.update(interview.id, {"r2_key": key})
        await self._db.commit()

        return InterviewUploadUrlResponse(
            upload_url=upload_url,
            expires_in_seconds=_UPLOAD_URL_EXPIRES_SECONDS,
        )

    async def _assert_recording_uploaded(self, interview: Interview) -> bool:
        """Refuse to complete an interview whose recording never arrived.

        r2_key is set when the upload URL is *issued*, so it proves nothing
        about a file existing. Only a definitive "missing or empty" blocks;
        if storage itself cannot be asked (network, permissions) we let the
        candidate through rather than lose a real interview to an outage.

        A strict interview that already has earlier recordings (kept across a reload, or from
        before it was reinstated) may end with nothing new to record, for example when the
        page comes back to find the last answer already given. It then completes with those.
        Returns False in that case when the final file is not to be used at all (the caller
        clears ``r2_key``, so no clip points at a file that is not there), True otherwise.
        """
        r2_key = interview.r2_key
        try:
            size = await get_storage_service().get_object_size(r2_key)
        except Exception:
            logger.warning(
                "Could not verify the uploaded recording at %s; allowing completion",
                r2_key,
                exc_info=True,
            )
            return True
        if not size:
            run = await self._strict().get_run(interview.id)
            if run is not None and run.recording_parts > 0:
                return True  # the earlier parts are joined in, so the key stays
            if run is not None and run.previous_recordings:
                return False  # the earlier attempts' clips are the recording; nothing new
            raise ValidationException(
                "We did not receive your recording. Please try uploading again.",
                code="RECORDING_NOT_RECEIVED",
            )
        return True

    async def _complete_upload(
        self,
        interview: Interview,
        transcript: str | None = None,
        realtime_usage: RealtimeUsageDetail | None = None,
    ):
        # Lock the row and read the status the database holds now, not the one
        # this request loaded earlier. Two completes arriving together both load
        # IN_PROGRESS; the lock makes the second wait for the first to commit
        # and then see UPLOADED, so scoring is queued exactly once.
        status = await self._repo.lock_status(interview.id)

        if status in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            # Already completed. A retried or replayed request must not reset
            # the status, re-queue scoring (more LLM cost) or overwrite the
            # saved transcript, so treat it as a successful no-op.
            await self._db.refresh(interview)
            return interview
        if status in ENDED_STATUSES:
            return await self._complete_ended(interview)
        if status not in (
            InterviewStatus.PENDING.value,
            InterviewStatus.IN_PROGRESS.value,
        ):
            raise ValidationException(
                "This interview can no longer accept a recording"
            )

        if not interview.r2_key:
            raise ValidationException("No upload was started for this interview")
        keep_recording = await self._assert_recording_uploaded(interview)

        # A strict interview's transcript is built here from the answers the server saved,
        # never taken from the browser, and there is no live voice session to cost.
        answers_complete = False
        if await self._strict().is_strict(interview.id):
            built = await self._strict().build_transcript(interview.id)
            if built is None:
                raise ValidationException("This interview has not been started.")
            transcript, answers_complete = built
            realtime_usage = None

        now = datetime.now(UTC)
        update_data: dict = {
            "status": InterviewStatus.UPLOADED.value,
            "completed_at": now,
            "video_expires_at": now
            + timedelta(days=settings.interview_video_retention_days),
        }
        if not keep_recording:
            update_data["r2_key"] = None
        # Only set if present — never overwrite an already-saved transcript
        # with a blank one on a defensive resend/retry.
        if transcript:
            update_data["transcript"] = transcript

        interview = await self._repo.update(interview.id, update_data)

        if answers_complete:
            # Every answer was transcribed from the audio here, so there is nothing sent by
            # the browser to check. This is recorded so the recording is not transcribed
            # (and paid for) a second time. When an answer is missing no check is recorded,
            # and the recording is transcribed to fill the gap.
            await self._repo.create_transcript_check(
                interview.id, TranscriptCheckStatus.SERVER_ONLY.value
            )

        if realtime_usage and (
            realtime_usage.input_tokens or realtime_usage.output_tokens
        ):
            usage_dict = realtime_usage.model_dump()
            await self._repo.create_cost_row(
                interview_id=interview.id,
                component=InterviewCostComponent.REALTIME.value,
                model=settings.realtime_model,
                input_tokens=realtime_usage.input_tokens,
                output_tokens=realtime_usage.output_tokens,
                usage_detail=usage_dict,
                cost_usd=compute_realtime_cost_usd(
                    settings.realtime_model, usage_dict
                ),
            )

        await self._db.commit()
        transcribe_and_score_interview_task.delay(str(interview.id))
        return interview

    async def _complete_ended(self, interview: Interview):
        """The recording of a strict interview that ended early has arrived.

        Keeps the evidence: the recording (joined with any parts kept across reloads), and the
        text of the answers as the server saved them. The interview stays ENDED_CONDUCT or
        STOPPED and is NOT scored, because the employer decides what happens to it (decision
        item 25). Safe to repeat: a second call changes nothing.
        """
        if interview.completed_at is not None:
            await self._db.refresh(interview)
            return interview
        if not interview.r2_key:
            raise ValidationException("No upload was started for this interview")
        keep_recording = await self._assert_recording_uploaded(interview)

        strict = self._strict()
        built = await strict.build_transcript(interview.id)
        now = datetime.now(UTC)
        update_data: dict = {
            "completed_at": now,
            "video_expires_at": now + timedelta(days=settings.interview_video_retention_days),
        }
        if not keep_recording:
            update_data["r2_key"] = None
        if built is not None:
            update_data["transcript"] = built[0]
        interview = await self._repo.update(interview.id, update_data)

        run = await strict.get_run(interview.id)
        needs_join = bool(run and run.recording_parts > 0)
        await self._db.commit()
        if needs_join:
            merge_interview_recording_task.delay(str(interview.id))
        return interview

    def _assert_interviews_enabled(self) -> None:
        """Refuse to start new interview work while the off switch is engaged.

        Deliberately not applied to uploading, completing or scoring, so a
        candidate who is already mid-interview can still finish.
        """
        if not settings.interview_enabled:
            raise ValidationException(
                "Interviews are temporarily unavailable. Please try again later.",
                code="AI_INTERVIEWS_DISABLED",
                status_code=503,
            )

    async def _charge_for_invite(
        self, job: Job, interview_id: uuid.UUID, *, again: bool = False
    ) -> None:
        """Take the interview's credits from the organization that owns the job,
        unless the interview is already paid. ``again`` takes them even so, for a
        completed interview the employer lets the candidate take a second time.

        Never charged: Elevare's own admin-owned jobs, a job whose owner has no
        organization (there is no wallet to take from), and a price of 0.
        Raises InsufficientCreditsException when the credits are short. Does not
        commit: the invite's own commit saves the charge with the interview.
        """
        cost = settings.interview_credit_cost
        employer = job.employer
        if (
            cost <= 0
            or employer is None
            or employer.role == UserRole.ADMIN.value
            or employer.organization_id is None
        ):
            return
        # Every organization pays the same way, a subscriber included: from the
        # credits its plan includes each month first, then from credits it bought.
        await CreditsService(self._db).charge_interview(
            employer.organization_id, interview_id, cost, again=again
        )

    async def _daily_invite_limit_reached(self, job: Job) -> bool:
        """Whether this job's organization has used up its first-time invites
        for the last 24 hours. A soft limit: two simultaneous bulk sends can
        overshoot it by a few, which is acceptable for a cost guard."""
        limit = settings.interview_daily_invite_limit
        if limit <= 0:
            return False
        employer = job.employer
        used = await self._repo.count_created_since(
            datetime.now(UTC) - timedelta(hours=24),
            organization_id=employer.organization_id if employer else None,
            employer_id=job.employer_id,
        )
        return used >= limit

    async def _send_invite_for_profile(self, job: Job, talent_pool_profile_id: uuid.UUID) -> dict:
        """
        Shared per-candidate send/resend logic used by send_invite and send_invites_to_all.
        """
        from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME
        from app.modules.notifications.repository import NotificationRepository

        if not await self._has_interview(job):
            raise ValidationException("This job does not have an interview configured")

        profile = await self._talent_pool_repo.get_by_id_joined_with_other_data(talent_pool_profile_id)
        candidate_email = resolve_candidate_email(profile) if profile else None
        if not candidate_email:
            return {"sent": False, "reason": "No email on file for this candidate"}

        # Checked before create_invite(), which always reissues a fresh
        # token — this tells us whether this is the first-ever invite
        # (Interview row doesn't exist yet) vs a resend, so the
        # candidate notification below only fires once, not on every
        # resend (including bulk "send to all" resends).
        is_first_invite = (
            await self._repo.get_by_job_and_profile(job.id, talent_pool_profile_id)
        ) is None

        # Only a first invite can start a new live session worth paying for;
        # a resend reuses the existing interview, so it is not counted.
        if is_first_invite and await self._daily_invite_limit_reached(job):
            return {
                "sent": False,
                "reason": (
                    "Daily interview invite limit reached. Please try again "
                    "tomorrow or contact support to raise it."
                ),
            }

        try:
            invite = await self.create_invite(job, talent_pool_profile_id)
        except InsufficientCreditsException as exc:
            return {"sent": False, "reason": exc.message}
        except ValidationException as exc:
            # A strict interview needs the job's questions, and one that ended early is
            # reinstated, not re-sent. Like short credits, that is said for this one
            # candidate, so a bulk send does not stop for everyone else.
            if exc.code not in ("INTERVIEW_QUESTIONS_MISSING", "INTERVIEW_ENDED_EARLY"):
                raise
            return {"sent": False, "reason": exc.message}
        if invite is None:
            return {"sent": False, "reason": "Interview already completed or not configured"}

        _interview, interview_url = invite

        organization = job.employer.organization if job.employer else None
        company_name = (
            organization.company_name
            if organization and organization.company_name
            else PLATFORM_COMPANY_NAME
        )

        is_self_registered = bool(profile.candidate_profile)

        # Always send the real, working no-login link. A self-registered
        # candidate having an account doesn't guarantee they have an
        # Application for *this* job (they may have been sourced straight
        # from Candidate Search / Talent Matches) — routing them to the
        # dashboard instead is a dead end whenever that's the case, so the
        # token link is the one path that's guaranteed to work for anyone.
        is_strict = await self._strict().is_strict(_interview.id)
        # Only a strict interview's email says what device it needs; a live one is sent
        # exactly as it always was.
        extra = {"strict": True} if is_strict else {}
        send_ai_interview_invite_email.delay(
            candidate_email=candidate_email,
            interview_url=interview_url,
            job_title=job.title,
            company_name=company_name,
            **extra,
        )

        if is_first_invite and is_self_registered:
            if is_strict:
                what_it_is = (
                    "The questions appear on your screen and you answer each one out "
                    "loud to your camera. Use a laptop or desktop computer with Chrome "
                    "or Edge. The employer reviews it afterward."
                )
                kind = "an interview"
            else:
                what_it_is = (
                    "It's a real-time voice conversation with an automated interviewer, "
                    "reviewed by the employer afterward."
                )
                kind = "a live interview"
            await NotificationRepository(self._db).create(
                recipient_id=profile.candidate_profile.user_id,
                type="AI_INTERVIEW_INVITE",
                title=f"Interview invite: {job.title}",
                body=(
                    f"{company_name} has invited you to {kind} for the "
                    f"{job.title} role. {what_it_is}\n\nStart here: {interview_url}"
                ),
                entity_type="APPLICATION" if _interview.application_id else None,
                entity_id=_interview.application_id,
            )
            await self._db.commit()

        return {"sent": True, "reason": None}

    async def send_invite(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> dict:
        """Explicit send/resend for one candidate."""
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        self._assert_interviews_enabled()

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()

        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")

        return await self._send_invite_for_profile(job, talent_pool_profile_id)

    async def invite_by_email(self, user: User, job_id: uuid.UUID, email: str) -> dict:
        """Send a job's AI interview to an email address, with no CV and no account needed.

        The address gets a row in the talent pool of its own (source ``interview_invite``) so
        the interview works like any other, and goes on the job's interview list, where it
        stays even when the email could not be sent (no credits, say) so it can be sent again
        from there. An address that belongs to a registered candidate uses their existing
        profile, and one typed before is reused, so there is never a second row for it.
        """
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository
        from app.modules.talent_pool.enums import SourceType, TalentPoolStatus

        self._assert_interviews_enabled()

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        if not await self._has_interview(job):
            raise ValidationException("This job does not have an interview configured")

        address = email.strip().lower()
        profile_id = await self._profile_for_email(user, address)
        if profile_id is None:
            profile = await self._talent_pool_repo.create(
                {
                    "source": SourceType.INTERVIEW_INVITE.value,
                    "source_note": "Invited to an interview by email",
                    "override_email": address,
                    "added_by": user.id,
                    "status": TalentPoolStatus.NEW.value,
                    "sourced_for_job_id": job.id,
                }
            )
            profile_id = profile.id

        await self._interview_list_repo.add(user.id, profile_id, job.id, None)
        await self._db.commit()

        result = await self._send_invite_for_profile(job, profile_id)
        return {**result, "talent_pool_profile_id": profile_id}

    async def _profile_for_email(self, user: User, address: str) -> uuid.UUID | None:
        """The pool row an email already has: a registered candidate's own, or one this employer
        made for it before. None when it has neither."""
        from app.modules.candidates.repository import CandidateRepository
        from app.modules.users.repository import UserRepository

        registered = await UserRepository(self._db).get_user_by_email(address)
        if registered is not None:
            candidate = await CandidateRepository(self._db).get_by_user_id(registered.id)
            if candidate is not None:
                existing = await self._talent_pool_repo.get_by_candidate_profile_id(candidate.id)
                if existing is not None:
                    return existing.id
        return await self._talent_pool_repo.find_interview_invite(user.id, address)

    async def get_pricing(self, user: User) -> dict:
        """What an AI interview costs the caller's organization, and its balance,
        so the screen can show both before an invite is sent. Uses the same rules
        as ``_charge_for_invite`` for who is never charged."""
        cost = settings.interview_credit_cost
        if (
            cost <= 0
            or user.role == UserRole.ADMIN.value
            or user.organization_id is None
        ):
            return {
                "credits_per_interview": cost,
                "balance": None,
                "charged": False,
                "included_in_plan": False,
                "plan_credits": None,
                "purchased_credits": None,
                "style": settings.interview_style,
            }
        balances = await CreditsService(self._db).get_balances(user.organization_id)
        return {
            "credits_per_interview": cost,
            "balance": balances["total"],
            "charged": True,
            # No plan makes interviews free any more; kept so a screen that has not
            # been updated yet still reads the response.
            "included_in_plan": False,
            "plan_credits": balances["plan_credits"],
            "purchased_credits": balances["purchased_credits"],
            "style": settings.interview_style,
        }

    async def get_interview_link(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> dict:
        """The candidate's interview link, for an employer to share themselves
        (the candidate may have no email on file, or the email may not arrive).

        Unlike a resend, this never disturbs a candidate who may be using the
        link right now: an unexpired link for an unfinished interview is returned
        as it is, and only a missing or expired one is created. Nothing is emailed.
        """
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        self._assert_interviews_enabled()

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()

        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")

        if not await self._has_interview(job):
            raise ValidationException("This job does not have an interview configured")

        interview = await self._repo.get_by_job_and_profile(job.id, talent_pool_profile_id)
        if interview is None:
            # Same cost guard as a first email invite.
            if await self._daily_invite_limit_reached(job):
                raise ValidationException(
                    "Daily interview invite limit reached. Please try again "
                    "tomorrow or contact support to raise it."
                )
        elif interview.status in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            raise ValidationException("This interview has already been completed")
        elif interview.status in ENDED_STATUSES:
            raise ValidationException(_ENDED_EARLY_MESSAGE, code="INTERVIEW_ENDED_EARLY")
        elif (
            interview.status
            in (InterviewStatus.PENDING.value, InterviewStatus.IN_PROGRESS.value)
            and interview.token
            and interview.token_expires_at
            and interview.token_expires_at > datetime.now(UTC)
        ):
            return {"interview_url": f"{settings.app_url}/interview/{interview.token}"}

        invite = await self.create_invite(job, talent_pool_profile_id)
        if invite is None:
            raise ValidationException("This interview has already been completed")

        _interview, interview_url = invite
        return {"interview_url": interview_url}

    async def send_invites_to_all(self, user: User, job_id: uuid.UUID) -> dict:
        """Bulk send/resend to everyone on this job's interview list."""
        from app.core.exceptions import JobNotFoundError
        from app.modules.interview_list.repository import InterviewListRepository
        from app.modules.jobs.repository import JobRepository

        self._assert_interviews_enabled()

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()

        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")

        # Everyone on the job's list, not only the entries this user added:
        # the job belongs to the organization, and a teammate may have added
        # the candidates.
        entries = await InterviewListRepository(self._db).list_all_for_job(job_id)

        sent = 0
        skipped = []
        for entry in entries:
            profile_id = entry.talent_pool_profile_id
            try:
                result = await self._send_invite_for_profile(job, profile_id)
            except ValidationException as exc:
                skipped.append({"talent_pool_profile_id": profile_id, "reason": str(exc)})
                continue
            if result["sent"]:
                sent += 1
            else:
                skipped.append({"talent_pool_profile_id": profile_id, "reason": result["reason"]})

        return {"sent": sent, "skipped": skipped}

    async def request_scoring(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> dict:
        """Queue AI scoring for a finished interview that has no score yet.

        The usual case: the interview was taken while the organization was on
        the Starter plan, so the transcript was saved but not scored. Everything
        scoring needs is already stored (the transcript and the job's brief), so
        this only re-runs the scoring step: the interview goes back to UPLOADED,
        which is the state the scoring task picks up, and the task (which is safe
        to run again) does the rest without telling the employer a second time
        that the interview completed.
        """
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")

        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None:
            raise InterviewNotFound()

        # Plan check first, so a Starter organization gets the upgrade message
        # instead of a silent no-op.
        await assert_can_score_interviews(self._db, job, interview.id)

        # Lock, then re-read: two clicks (or a click racing the task) must not
        # both queue scoring. The second sees the interview already processing.
        await self._repo.lock_status(interview.id)
        await self._db.refresh(interview)
        failed_scoring = False

        if interview.status == InterviewStatus.UPLOADED.value:
            # Normally being scored right now. Only if it has sat there for a
            # long time (a worker died mid-run) is it safe to queue it again.
            if interview.updated_at > datetime.now(UTC) - _SCORING_STUCK_AFTER:
                raise ValidationException(
                    "This interview is still being processed. Please check back in a minute.",
                    code="INTERVIEW_PROCESSING",
                )
        elif interview.status in ENDED_STATUSES:
            # The employer asks for a score of an interview that ended early (decision item
            # 25: never automatic). It then counts as finished, so it can no longer be
            # reinstated; the notes about how it ended stay with it. The recording must have
            # arrived and any joining of its parts be done first.
            run = await self._strict().get_run(interview.id)
            if interview.completed_at is None or (run and run.recording_parts > 0):
                raise ValidationException(
                    "The recording of this interview is still being prepared. "
                    "Please check back in a minute.",
                    code="INTERVIEW_PROCESSING",
                )
        elif (
            interview.status == InterviewStatus.FAILED.value
            and interview.completed_at is not None
        ):
            # Scoring failed after the recording arrived (an interview that was never completed
            # is recovered, not rescored). The recording and the transcript are kept, and the
            # task transcribes the recording itself when there is no transcript.
            failed_scoring = True
        elif interview.status != InterviewStatus.SCORED.value:
            raise ValidationException(
                "This interview has not been completed yet.",
                code="INTERVIEW_NOT_COMPLETED",
            )
        elif interview.ai_score is not None:
            raise ValidationException(
                "This interview already has a score.",
                code="INTERVIEW_ALREADY_SCORED",
            )

        if not interview.transcript and not (failed_scoring and interview.r2_key):
            raise ValidationException(
                "There is no transcript to score for this interview.",
                code="INTERVIEW_NO_TRANSCRIPT",
            )

        if failed_scoring:
            # The credits were given back when scoring failed, so they are taken again for the
            # retry (nothing is taken while the interview is still paid). Short on credits: 402
            # and nothing changes. Saved with the status change below.
            await self._charge_for_invite(job, interview.id)

        await self._repo.update(interview.id, {"status": InterviewStatus.UPLOADED.value})
        await self._db.commit()
        # The employer was never told a failed interview completed, so this run tells them.
        transcribe_and_score_interview_task.delay(str(interview.id), notify=failed_scoring)
        return {"queued": True}

    async def request_rescore(
        self, user: User, job_id: uuid.UUID, talent_pool_profile_id: uuid.UUID
    ) -> dict:
        """Queue a second scoring of an interview that is already scored, from its stored
        transcript (decision item 58). Elevare admin only, for any job. One more model call at
        Elevare's cost: the candidate and the company are not charged, and the employer is not
        told. The interview stays scored while it runs, so the earlier result shows until the new
        one replaces it; if the call fails nothing changes. The earlier system result and the
        admin's edits stay in the review history."""
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        if user.role != UserRole.ADMIN.value:
            raise PermissionDeniedException("Only an Elevare administrator can score an interview again")
        if await JobRepository(self._db).get_by_id(job_id) is None:
            raise JobNotFoundError()
        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None:
            raise InterviewNotFound()
        # Under the interview's row lock, so two clicks (or two admins) cannot both start a scoring:
        # the second finds the first still pending and is refused.
        await self._repo.lock_status(interview.id)
        await self._db.refresh(interview)
        if interview.status != InterviewStatus.SCORED.value:
            raise ValidationException(
                "Only a scored interview can be scored again.", code="INTERVIEW_NOT_SCORED"
            )
        if not interview.transcript:
            raise ValidationException(
                "There is no transcript to score for this interview.", code="INTERVIEW_NO_TRANSCRIPT"
            )
        now = datetime.now(UTC)
        row = (
            await self._db.execute(select(InterviewRescore).where(InterviewRescore.interview_id == interview.id))
        ).scalar_one_or_none()
        if row is not None and row.status == RESCORE_PENDING and now - row.requested_at < RESCORE_STALE_AFTER:
            raise ValidationException(
                "This interview is already being scored again. Please wait for it to finish.",
                code="RESCORE_IN_PROGRESS",
            )
        if row is None:
            row = InterviewRescore(interview_id=interview.id, status=RESCORE_PENDING, requested_at=now)
            self._db.add(row)
        row.status, row.requested_by, row.requested_at = RESCORE_PENDING, user.id, now
        row.finished_at, row.error = None, None
        await self._db.commit()

        name = " ".join(f"{user.first_name} {user.last_name}".split()) or user.email
        try:
            rescore_interview_task.delay(str(interview.id), str(user.id), name)
        except Exception:
            # Never leave a request pending that nothing is working on.
            logger.exception("interview rescore could not be queued: interview=%s", interview.id)
            row.status, row.finished_at = RESCORE_FAILED, datetime.now(UTC)
            row.error = "The request could not be queued. Please try again."
            await self._db.commit()
            raise
        logger.info("interview rescore queued: interview=%s by admin=%s", interview.id, user.id)
        return {"queued": True}

    async def _rescore_state(self, interview_id: uuid.UUID) -> dict | None:
        """For an admin: whether this interview is being scored again (PENDING), the last request
        did not work (FAILED, or PENDING for so long it was lost: ``stale``), or nothing is open
        (None, also after a request that finished). Guarded for the seconds of a deploy before the
        table exists."""

        async def read() -> dict | None:
            row = (
                await self._db.execute(select(InterviewRescore).where(InterviewRescore.interview_id == interview_id))
            ).scalar_one_or_none()
            if row is None or row.status == RESCORE_DONE:
                return None
            stale = row.status == RESCORE_PENDING and datetime.now(UTC) - row.requested_at >= RESCORE_STALE_AFTER
            return {
                "status": row.status,
                "requested_at": row.requested_at,
                "error": row.error,
                "stale": stale,
            }

        return await tolerate_missing(self._db, read, None)

    async def get_monthly_cost_summary(self) -> dict:
        """Return the current month's interview cost, broken down by component
        (realtime/transcription/scoring) — realtime is the dominant cost, this
        is what makes it visible instead of a single opaque total.

        ``total_cost_usd`` is None whenever any component with calls this
        month has an unpriced model — summing only the known components
        and calling that "the total" would understate real spend without
        any indication it's incomplete. Better to surface "unknown" than a
        confident-looking number that's actually a lower bound.
        """
        rows = await self._repo.get_monthly_cost_summary()
        by_component = {
            row.component: {
                "total_cost_usd": float(row.total_cost) if row.total_cost is not None else None,
                "total_calls": row.total_calls or 0,
            }
            for row in rows
        }
        has_unpriced_calls = any(
            v["total_cost_usd"] is None and v["total_calls"] > 0
            for v in by_component.values()
        )
        total_cost_usd = (
            None
            if has_unpriced_calls
            else sum((v["total_cost_usd"] or 0.0 for v in by_component.values()), 0.0)
        )
        total_calls = sum(v["total_calls"] for v in by_component.values())
        return {
            "month": datetime.now(UTC).strftime("%Y-%m"),
            "total_cost_usd": total_cost_usd,
            "total_calls": total_calls,
            "by_component": by_component,
        }

    async def get_cost_trend(
        self, from_date: date | None = None, to_date: date | None = None
    ) -> dict:
        """Return a gap-free monthly series, each point broken down by
        component the same way get_monthly_cost_summary is — see that
        docstring for the null/zero cost rules, applied per-month here."""
        rows = await self._repo.get_cost_trend(from_date, to_date)

        by_month: dict[str, dict] = {}
        for row in rows:
            m = row.month.strftime("%Y-%m")
            by_month.setdefault(m, {})[row.component] = {
                "total_cost_usd": float(row.total_cost) if row.total_cost is not None else None,
                "total_calls": row.total_calls or 0,
            }

        bounds = effective_month_bounds(list(by_month.keys()), from_date, to_date)
        if bounds is None:
            return {"series": []}

        start_month, end_month = bounds
        months = month_range(
            date.fromisoformat(start_month + "-01"),
            date.fromisoformat(end_month + "-01"),
        )

        component_keys = [c.value for c in InterviewCostComponent]
        series = []
        for m in months:
            month_components = by_month.get(m, {})
            by_component = {
                key: month_components.get(
                    key, {"total_cost_usd": 0.0, "total_calls": 0}
                )
                for key in component_keys
            }
            has_unpriced_calls = any(
                v["total_cost_usd"] is None and v["total_calls"] > 0
                for v in by_component.values()
            )
            total_cost_usd = (
                None
                if has_unpriced_calls
                else sum((v["total_cost_usd"] or 0.0 for v in by_component.values()), 0.0)
            )
            total_calls = sum(v["total_calls"] for v in by_component.values())
            series.append(
                {
                    "month": m,
                    "total_cost_usd": total_cost_usd,
                    "total_calls": total_calls,
                    "by_component": by_component,
                }
            )
        return {"series": series}

    async def get_detail_for_employer(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> InterviewDetailResponse:
        """Employer views transcript/score/video for one candidate's completed interview."""
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()
        # An Elevare administrator may open any account's interview (to review a score); everyone
        # else only a job their company manages.
        if user.role != UserRole.ADMIN.value and not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")

        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        # An interview that ended early is shown too: the employer needs its recording and its
        # conduct notes to decide whether to reinstate it.
        if interview is None or interview.status not in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
            *ENDED_STATUSES,
        ):
            raise InterviewNotFound()

        return await self.build_detail(
            job, interview, include_review_history=user.role == UserRole.ADMIN.value
        )

    async def build_detail(
        self,
        job: Job,
        interview: Interview,
        *,
        video_seconds: int = 3600,
        include_panel_decision: bool = True,
        include_review_history: bool = False,
    ) -> InterviewDetailResponse:
        """The full detail of a completed interview: recording, transcript, the AI's
        assessment of it and the CV assessment next to it.

        Does no permission check: the caller has already decided the reader may see
        this (the employer's own detail view, and the shared results link). Shared so
        both show exactly the same thing. ``video_seconds`` is how long the recording
        link works; a link meant to be passed around uses a much shorter one.
        ``include_panel_decision`` is false for the shared link: the company's own panel
        decision and rationale are internal, not part of what an outside reader is shown.
        ``include_review_history`` is true only for an Elevare admin: the system's own score and
        band and who reviewed the score are not shown to anyone else.

        A reviewed score (decision item 52) replaces the system's in the score, the weighted report
        and the written assessment, for the employer and the shared link alike.
        """
        strict = await self._strict().strict_detail(interview)
        # The weighted score report, for an interview scored with a scoring profile.
        async def read_report() -> dict | None:
            result = await self._db.execute(
                select(InterviewWeightedScore.report).where(
                    InterviewWeightedScore.interview_id == interview.id
                )
            )
            return result.scalar_one_or_none()

        stored_report = await tolerate_missing(self._db, read_report, None) or {}
        # The stored report holds the weighted score and, apart from it, the practical case and the
        # content of the assessment record (top strengths and gaps, what to verify, referee questions).
        score_report = (
            {key: value for key, value in stored_report.items() if key not in ("practical", "record")}
            if "rows" in stored_report
            else None
        )
        practical_case = stored_report.get("practical")
        reviews = await self._score_reviews(interview.id)
        shown = apply_review(
            score=interview.ai_score,
            rationale=interview.ai_rationale,
            report=score_report,
            review_score=reviews[0].score if reviews else None,
            review_ratings=(reviews[0].ratings or {}) if reviews else None,
            review_rationale=reviews[0].rationale if reviews else None,
        )
        # The job's switch: with scores off, the employer and the shared link are not sent the
        # total, the band, the practical case's total or the assessment lines that state them. An
        # Elevare admin (the only reader with the review history) always gets the real values.
        scores_hidden = not include_review_history and not await self._scores_visible(job.id)
        shown_score, shown_rationale, shown_report = shown.score, shown.rationale, shown.report
        # A scorecard an admin filled in by hand counts as a review on its own (the "Reviewed" tag).
        reviewed = shown.reviewed or bool(reviews and reviews[0].scorecard)
        if scores_hidden:
            hidden = hide_scores(
                rationale=shown.rationale, report=shown.report, practical=practical_case
            )
            shown_score, shown_rationale = hidden.score, hidden.rationale
            shown_report, practical_case = hidden.report, hidden.practical
            reviewed = False
        # The job's other display switches (item 61), for an employer and the shared link only: the
        # score number (the band and the 1 to 5 ratings stay), the gaps and risks, and the written
        # assessment. With the scores switched off altogether the band is gone already.
        display = await self._display_flags(job.id)
        number_hidden = not scores_hidden and not include_review_history and not display["show_score_number"]
        if number_hidden:
            hidden = hide_numbers(rationale=shown_rationale, report=shown_report, practical=practical_case)
            shown_score, shown_rationale = hidden.score, hidden.rationale
            shown_report, practical_case = hidden.report, hidden.practical
        gaps_hidden = not include_review_history and not display["show_gaps"]
        if gaps_hidden:
            shown_rationale = strip_gaps(shown_rationale)
        writeup_hidden = not include_review_history and not display["show_writeup"]
        if writeup_hidden:
            shown_rationale = None
        video_url = None
        # While the pieces of the recording are being joined the file on record is only the last
        # piece: showing it would look like the whole interview, so nothing is shown yet.
        joining = bool(strict and strict["recording_pending"])
        if interview.r2_key and not joining:
            video_url = await get_storage_service().generate_presigned_url(
                interview.r2_key, expires_seconds=video_seconds,
            )
        # A reinstated interview keeps each attempt's recording as its own clip.
        clips: list[RecordingClip] = []
        run = await self._strict().get_run(interview.id)
        for key in (run.previous_recordings or []) if run is not None else []:
            clips.append(
                RecordingClip(
                    attempt=attempt_of_key(key),
                    video_url=await get_storage_service().generate_presigned_url(
                        key, expires_seconds=video_seconds,
                    ),
                )
            )
        if video_url:
            clips.append(RecordingClip(attempt=run.attempt if run else 1, video_url=video_url))

        cv_score, cv_strengths, cv_weaknesses, cv_fit_summary = (
            await self.resolve_cv_assessment(
                job, interview.talent_pool_profile, interview.application_id
            )
        )
        record = await self._assessment_record(
            job,
            interview,
            run,
            stored_report.get("record") or {},
            include_panel_decision=include_panel_decision,
        )
        if gaps_hidden:
            record["top_gaps"] = []
        # The scorecard as Elevare prints it: built from what is shown (a reviewed rating or total
        # included) and what an admin filled in by hand.
        scorecard = build_scorecard(
            report=shown_report,
            practical=practical_case,
            admin=reviews[0].scorecard if reviews else None,
            top_strengths=record.get("top_strengths") or [],
            panel_decision=((record.get("panel_decision") or {}).get("label")),
            total=shown.score,
            hidden=scores_hidden or number_hidden,
            show_summary=await self._summary_shown(job.id),
        )

        # A transcript that did not match the recording is not shown: the
        # employer sees the recording's own transcript, which is also what
        # the score was based on.
        check = await self._repo.get_transcript_check(interview.id)
        transcript = interview.transcript
        if (
            check is not None
            and check.status == TranscriptCheckStatus.MISMATCH.value
            and check.server_transcript
        ):
            transcript = check.server_transcript

        return InterviewDetailResponse(
            status=interview.status,
            transcript=transcript,
            transcript_check=check.status if check else None,
            ai_score=shown_score,
            ai_rationale=shown_rationale,
            ai_scored_at=interview.ai_scored_at,
            reviewed=reviewed,
            scores_hidden=scores_hidden,
            score_number_hidden=number_hidden,
            gaps_hidden=gaps_hidden,
            writeup_hidden=writeup_hidden,
            rescore=await self._rescore_state(interview.id) if include_review_history else None,
            score_review=(
                self._score_review_history(interview, stored_report, reviews)
                if include_review_history
                else None
            ),
            video_url=video_url,
            recordings=clips,
            score_report=shown_report,
            practical_case=practical_case,
            record=record,
            completed_at=interview.completed_at,
            cv_score=cv_score,
            cv_strengths=cv_strengths,
            cv_weaknesses=cv_weaknesses,
            cv_fit_summary=cv_fit_summary,
            strict=strict,
            scorecard=scorecard,
        )

    async def _assessment_record(
        self, job: Job, interview: Interview, run, content: dict, *, include_panel_decision: bool
    ) -> dict:
        """The candidate assessment record (Section 7 of the client's pack): the header, the top
        three strengths and gaps, what to verify and ask referees, from what was stored when the
        interview was scored, and the panel's latest decision if it is to be shown. An interview
        scored before the record was kept has the header and nothing else."""
        started = run.started_at if run is not None else None
        finished = interview.completed_at
        last_answered = None
        if run is not None:
            last_answered = (
                await self._db.execute(
                    select(func.max(InterviewTurn.answered_at)).where(
                        InterviewTurn.interview_id == interview.id
                    )
                )
            ).scalar_one_or_none()
        minutes = minutes_spent(started, run.ended_at if run is not None else None, last_answered)

        def listed(name: str) -> list[str]:
            value = content.get(name)
            return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, list) else []

        return {
            "reference": f"EL-{interview.id.hex[:8].upper()}",
            "role": job.title,
            "interview_date": finished or started,
            "duration_minutes": minutes,
            "interviewer": RECORD_INTERVIEWER,
            "top_strengths": listed("strengths")[:3],
            "top_gaps": listed("gaps")[:3],
            "claims_to_verify": listed("claims_to_verify"),
            "reference_check_questions": listed("reference_check_questions"),
            "panel_decision": await self._latest_panel_decision(interview.id) if include_panel_decision else None,
        }

    async def _scores_visible(self, job_id: uuid.UUID) -> bool:
        """Whether the job shows its interview score and provisional band: true unless somebody
        switched them off (and in the seconds of a deploy before the table exists)."""

        async def read() -> bool:
            row = (
                await self._db.execute(
                    select(JobScoreVisibility.show_scores).where(JobScoreVisibility.job_id == job_id)
                )
            ).scalar_one_or_none()
            return True if row is None else bool(row)

        return await tolerate_missing(self._db, read, True)

    async def get_score_visibility(
        self, user: User, job_id: uuid.UUID
    ) -> dict:
        """Whether a job's interview score and provisional band are shown. For the job's company or
        an Elevare admin."""
        job = await self._job_for_visibility(user, job_id)
        return {"show_scores": await self._scores_visible(job.id)}

    async def set_score_visibility(
        self, user: User, job_id: uuid.UUID, show_scores: bool
    ) -> dict:
        """Switch a job's interview score and provisional band on or off, for the job's company or
        an Elevare admin (decision item 54). The scores are still worked out and kept; this only
        decides whether the employer's screens and the shared link are sent them. Logged."""
        job = await self._job_for_visibility(user, job_id)
        existing = (
            await self._db.execute(select(JobScoreVisibility).where(JobScoreVisibility.job_id == job.id))
        ).scalar_one_or_none()
        if existing is None:
            self._db.add(JobScoreVisibility(job_id=job.id, show_scores=show_scores, changed_by=user.id))
        else:
            existing.show_scores = show_scores
            existing.changed_by = user.id
        await self._db.commit()
        logger.info(
            "interview scores %s: job=%s by user=%s", "shown" if show_scores else "hidden", job.id, user.id
        )
        return {"show_scores": show_scores}

    async def _display_flags(self, job_id: uuid.UUID) -> dict[str, bool]:
        """Which parts of the job's interview results an employer and the shared link are shown:
        the score number, the gaps and risks, the written assessment. All true unless an admin
        switched one off (and in the seconds of a deploy before the columns exist)."""
        shown = {"show_score_number": True, "show_gaps": True, "show_writeup": True}

        async def read() -> dict[str, bool]:
            row = (
                await self._db.execute(
                    select(
                        JobScoreVisibility.show_score_number,
                        JobScoreVisibility.show_gaps,
                        JobScoreVisibility.show_writeup,
                    ).where(JobScoreVisibility.job_id == job_id)
                )
            ).one_or_none()
            if row is None:
                return shown
            return dict(zip(shown, (bool(value) for value in row), strict=True))

        return await tolerate_missing(self._db, read, shown)

    async def get_result_display(self, user: User, job_id: uuid.UUID) -> dict:
        """Which parts of a job's interview results are shown. Elevare admin only."""
        job = await self._job_for_summary(user, job_id)
        return await self._display_flags(job.id)

    async def set_result_display(self, user: User, job_id: uuid.UUID, changes: dict[str, bool]) -> dict:
        """Switch the score number, the gaps and risks and/or the written assessment of a job's
        interview results on or off (decision item 61); only the fields given change. Elevare admin
        only. Nothing is deleted: the scores, the gaps and the text are still worked out and kept,
        and an admin always sees them. Logged."""
        job = await self._job_for_summary(user, job_id)
        if not changes:
            raise ValidationException("Say which setting to change.", code="NOTHING_TO_CHANGE")
        existing = (
            await self._db.execute(select(JobScoreVisibility).where(JobScoreVisibility.job_id == job.id))
        ).scalar_one_or_none()
        if existing is None:
            self._db.add(JobScoreVisibility(job_id=job.id, changed_by=user.id, **changes))
        else:
            for name, value in changes.items():
                setattr(existing, name, value)
            existing.changed_by = user.id
        await self._db.commit()
        logger.info("interview result display changed: job=%s by user=%s %s", job.id, user.id, changes)
        return await self._display_flags(job.id)

    async def _summary_shown(self, job_id: uuid.UUID) -> bool:
        """Whether the job's scorecard prints its Evaluation Summary: true unless an admin switched
        it off (and in the seconds of a deploy before the column exists)."""

        async def read() -> bool:
            row = (
                await self._db.execute(
                    select(JobScoreVisibility.show_summary).where(JobScoreVisibility.job_id == job_id)
                )
            ).scalar_one_or_none()
            return True if row is None else bool(row)

        return await tolerate_missing(self._db, read, True)

    async def get_scorecard_summary(self, user: User, job_id: uuid.UUID) -> dict:
        """Whether a job's scorecard shows its Evaluation Summary. Elevare admin only."""
        job = await self._job_for_summary(user, job_id)
        return {"show_summary": await self._summary_shown(job.id)}

    async def set_scorecard_summary(self, user: User, job_id: uuid.UUID, show_summary: bool) -> dict:
        """Switch a job's scorecard Evaluation Summary on or off (decision item 57). Admin only. What
        was filled in by hand is kept; this only decides whether the scorecard shows it. Logged."""
        job = await self._job_for_summary(user, job_id)
        existing = (
            await self._db.execute(select(JobScoreVisibility).where(JobScoreVisibility.job_id == job.id))
        ).scalar_one_or_none()
        if existing is None:
            self._db.add(JobScoreVisibility(job_id=job.id, show_summary=show_summary, changed_by=user.id))
        else:
            existing.show_summary = show_summary
            existing.changed_by = user.id
        await self._db.commit()
        logger.info(
            "scorecard summary %s: job=%s by user=%s", "shown" if show_summary else "hidden", job.id, user.id
        )
        return {"show_summary": show_summary}

    async def recalculate_bands(self, user: User, job_id: uuid.UUID) -> dict:
        """Weigh every scored interview of a job again under the job's CURRENT scoring profile
        (its weights, key marks, minimum key rating and band cut-offs), using the ratings already
        saved. No model call and no rating changes; the total, the band, the key-competency flags
        and the lines of the written assessment that state them follow the profile. Elevare admin
        only (decision item 63). Interviews being scored again right now, and ones with no
        competency ratings, are skipped. Safe to run twice: the second run changes nothing. An admin's
        reviewed total, ratings or text are untouched (the band of a reviewed total follows the new
        cut-offs). Logged."""
        from app.modules.interviews.band_recalculation import (
            WEIGHTED_KEYS,
            recalculate,
            retarget_text,
        )
        from app.modules.interviews.scoring_profile_service import load_profile

        job = await self._job_for_summary(user, job_id)
        profile = await load_profile(self._db, job.id)
        if profile is None:
            raise ValidationException(
                "This job has no scoring profile, so there is nothing to weigh the ratings by.",
                code="NO_SCORING_PROFILE",
            )
        saved = (
            await self._db.execute(
                select(Interview, InterviewWeightedScore)
                .join(InterviewWeightedScore, InterviewWeightedScore.interview_id == Interview.id)
                .where(Interview.job_id == job.id, Interview.status == InterviewStatus.SCORED.value)
                .order_by(Interview.created_at)
                .limit(2000)
            )
        ).all()

        checked = changed = unchanged = incomplete = skipped = 0
        changes: list[dict] = []
        now = datetime.now(UTC)
        for interview, stored in saved:
            checked += 1
            # Take the interview's lock, so this and a scoring run take turns, then read it again.
            await self._repo.lock_status(interview.id)
            await self._db.refresh(interview)
            await self._db.refresh(stored)
            pending = await self._rescore_state(interview.id)
            if interview.status != InterviewStatus.SCORED.value or (
                pending and pending["status"] == RESCORE_PENDING and not pending["stale"]
            ):
                skipped += 1
                continue
            old = stored.report or {}
            fresh = recalculate(old, profile.competencies, profile.bands, profile.key_min_rating)
            if fresh is None:
                skipped += 1
                continue
            if all(fresh.get(key) == old.get(key) for key in WEIGHTED_KEYS):
                unchanged += 1
                continue
            changed += 1
            if not fresh["complete"]:
                incomplete += 1
            changes.append(
                {
                    "talent_pool_profile_id": interview.talent_pool_profile_id,
                    "from_score": old.get("score"),
                    "to_score": fresh["score"],
                    "from_band": old.get("band"),
                    "to_band": fresh["band"],
                }
            )
            fresh["recalculated"] = {
                "at": now.isoformat(),
                "by": str(user.id),
                "from_score": old.get("score"),
                "from_band": old.get("band"),
            }
            stored.report = fresh
            interview.ai_score = fresh["score"]
            interview.ai_rationale = retarget_text(interview.ai_rationale, fresh)
        await self._db.commit()
        logger.info(
            "interview bands recalculated: job=%s by user=%s checked=%d changed=%d unchanged=%d skipped=%d",
            job.id, user.id, checked, changed, unchanged, skipped,
        )
        return {
            "checked": checked,
            "changed": changed,
            "unchanged": unchanged,
            "incomplete": incomplete,
            "skipped": skipped,
            "changes": changes,
        }

    async def _job_for_summary(self, user: User, job_id: uuid.UUID) -> Job:
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        if user.role != UserRole.ADMIN.value:
            raise PermissionDeniedException("Only an Elevare administrator can change this setting")
        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()
        return job

    async def _job_for_visibility(self, user: User, job_id: uuid.UUID) -> Job:
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()
        if user.role != UserRole.ADMIN.value and not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        return job

    async def _score_reviews(self, interview_id: uuid.UUID) -> list[InterviewScoreReview]:
        """The reviews of an interview's score, newest first (empty in the seconds of a deploy
        before the table exists, so the system's own result is shown)."""

        async def read() -> list[InterviewScoreReview]:
            result = await self._db.execute(
                select(InterviewScoreReview)
                .where(InterviewScoreReview.interview_id == interview_id)
                .order_by(InterviewScoreReview.reviewed_at.desc(), InterviewScoreReview.created_at.desc())
            )
            return list(result.scalars().all())

        return await tolerate_missing(self._db, read, [])

    @staticmethod
    def _score_review_history(
        interview: Interview, stored_report: dict, reviews: list[InterviewScoreReview]
    ) -> dict:
        """For an Elevare admin only: the system's own score and band, and every review of it.
        The original is read from what was stored when the interview was scored, so it stays the
        system's whatever was reviewed since."""
        return {
            "original_score": interview.ai_score,
            "original_band": stored_report.get("band"),
            # The system's own rating of each competency, to compare the reviewer's against.
            "original_ratings": {row["name"]: row.get("rating") for row in stored_report.get("rows", [])},
            # The system's own written assessment, which is kept whatever an admin wrote in its place.
            "original_rationale": interview.ai_rationale,
            # What the system wrote for each competency's Evidence / Verification, to compare with.
            "original_evidence": {row["name"]: system_evidence(row) for row in stored_report.get("rows", [])},
            "reviews": [
                {
                    "score": row.score,
                    "ratings": row.ratings or {},
                    "rationale_changed": bool(row.rationale),
                    "scorecard_changed": bool(row.scorecard),
                    "reason": row.reason,
                    "reviewed_by_name": row.reviewed_by_name,
                    "reviewed_at": row.reviewed_at,
                }
                for row in reviews
            ],
        }

    @staticmethod
    def _clean_scorecard(scorecard: dict | None, report: dict) -> dict:
        """The hand-filled scorecard fields as they are kept: evidence under each competency's own
        name (an unknown name is refused), a practical rating in half steps, the strengths and the
        decision wording, trimmed, with anything empty left out."""
        if not scorecard:
            return {}
        kept: dict = {}
        evidence = scorecard.get("evidence") or {}
        if evidence:
            rows = {row["name"].casefold(): row["name"] for row in report.get("rows", [])}
            if not rows:
                raise ValidationException(
                    "This interview was not scored on competencies, so there is no evidence to fill in.",
                    code="NO_COMPETENCIES",
                )
            cleaned: dict[str, str] = {}
            for given, text in evidence.items():
                name = rows.get(str(given).casefold())
                if name is None:
                    raise ValidationException(
                        f"\"{given}\" is not a competency of this interview.", code="UNKNOWN_COMPETENCY"
                    )
                line = " ".join(str(text).split())
                if len(line) > 1000:
                    raise ValidationException(
                        "The evidence for a competency can be at most 1000 characters.", code="EVIDENCE_TOO_LONG"
                    )
                if line:
                    cleaned[name] = line
            if cleaned:
                kept["evidence"] = cleaned
        practical = scorecard.get("practical_rating")
        if practical is not None:
            if not valid_rating(practical):
                raise ValidationException(
                    "The practical case rating must be from 1 to 5, in steps of a half (for example 3.5).",
                    code="INVALID_RATING",
                )
            kept["practical_rating"] = clean_rating(practical)
        strengths = "\n".join(line.strip() for line in str(scorecard.get("strengths") or "").splitlines() if line.strip())
        if strengths:
            kept["strengths"] = strengths
        decision = " ".join(str(scorecard.get("decision") or "").split())
        if decision:
            kept["decision"] = decision
        return kept

    async def review_score(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        score: int | None,
        reason: str | None,
        ratings: dict | None = None,
        rationale: str | None = None,
        scorecard: dict | None = None,
        *,
        clear: bool = False,
    ) -> dict:
        """An Elevare admin changes the competency ratings, sets the total and/or writes the written
        assessment of a scored interview in place of the system's, or (``clear``) takes the review
        away again. The total follows the ratings by the system's formula unless one was typed, and
        the band follows the total by the job's cut-offs. A written assessment is shown as written,
        in place of the system's text, which is kept.

        Admin only, for any job (decision item 52). Append-only: each change is a new row with who
        made it, when, the optional reason, the ratings that differ from the system's and the
        system's own score and band, and is also written to the log. Only a scored interview:
        there is nothing to review before that.
        """
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        if user.role != UserRole.ADMIN.value:
            raise PermissionDeniedException("Only an Elevare administrator can review a score")
        if score is not None and not (MIN_SCORE <= score <= MAX_SCORE):
            raise ValidationException(
                f"The score must be between {MIN_SCORE} and {MAX_SCORE}.", code="INVALID_SCORE"
            )
        cleaned_rationale = rationale.strip() if rationale else None
        if not clear and score is None and not ratings and not cleaned_rationale and not scorecard:
            raise ValidationException(
                "Set a score, change a rating, edit the written assessment or fill in the scorecard.",
                code="NOTHING_TO_REVIEW",
            )
        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()
        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None:
            raise InterviewNotFound()

        await self._repo.lock_status(interview.id)
        await self._db.refresh(interview)
        if interview.status != InterviewStatus.SCORED.value:
            raise ValidationException(
                "Only a scored interview can have its score reviewed.",
                code="INTERVIEW_NOT_SCORED",
            )

        report = (
            await self._db.execute(
                select(InterviewWeightedScore.report).where(
                    InterviewWeightedScore.interview_id == interview.id
                )
            )
        ).scalar_one_or_none() or {}

        # Only the ratings that differ from the system's own are kept, under the competency's own
        # name. A name the job's profile does not have, or a rating outside 1 to 5, is refused.
        changed: dict[str, int | float] = {}
        # The hand-filled scorecard fields, tidied: only what was filled in is kept.
        filled = self._clean_scorecard(scorecard, report)
        # A written assessment equal to the system's own is no change: the system's text is shown.
        edited_rationale = (
            cleaned_rationale
            if cleaned_rationale and cleaned_rationale != (interview.ai_rationale or "").strip()
            else None
        )
        if ratings:
            rows = {row["name"].casefold(): row for row in report.get("rows", [])}
            if not rows:
                raise ValidationException(
                    "This interview was not scored on competencies, so there are no ratings to change.",
                    code="NO_COMPETENCIES",
                )
            for given, rating in ratings.items():
                row = rows.get(str(given).casefold())
                if row is None:
                    raise ValidationException(
                        f"\"{given}\" is not a competency of this interview.", code="UNKNOWN_COMPETENCY"
                    )
                if not valid_rating(rating):
                    raise ValidationException(
                        "A rating must be from 1 to 5, in steps of a half (for example 3.5).",
                        code="INVALID_RATING",
                    )
                if clean_rating(rating) != row.get("rating"):
                    changed[row["name"]] = clean_rating(rating)
            if score is None and not changed and not edited_rationale and not filled:
                raise ValidationException(
                    "Those ratings are the system's own, so there is nothing to change.", code="NOTHING_TO_REVIEW"
                )
        if not clear and score is None and not changed and not edited_rationale and not filled:
            raise ValidationException(
                "That written assessment is the system's own, so there is nothing to change.",
                code="NOTHING_TO_REVIEW",
            )
        # With the Evaluation Summary switched off the panel does not offer its fields, and a save
        # replaces the whole review, so what was filled in before is carried over, not lost. Not on
        # a removal, which clears the review.
        if not clear and not await self._summary_shown(job.id):
            previous = await self._score_reviews(interview.id)
            earlier = (previous[0].scorecard or {}) if previous else {}
            for key in ("practical_rating", "strengths", "decision"):
                if key not in filled and earlier.get(key) not in (None, ""):
                    filled[key] = earlier[key]
        name = " ".join(f"{user.first_name} {user.last_name}".split()) or user.email
        cleaned_reason = " ".join(reason.split()) if reason else None
        row = InterviewScoreReview(
            interview_id=interview.id,
            score=score,
            ratings=changed or None,
            rationale=edited_rationale,
            scorecard=filled or None,
            reason=cleaned_reason or None,
            reviewed_by=user.id,
            reviewed_by_name=name[:200],
            reviewed_at=datetime.now(UTC),
            original_score=interview.ai_score,
            original_band=report.get("band"),
        )
        self._db.add(row)
        await self._db.commit()
        logger.info(
            "interview score %s: interview=%s by admin=%s (system score %s, band %s, now score %s, "
            "ratings %s, written assessment %s)",
            "review removed" if clear else "reviewed",
            interview.id,
            user.id,
            interview.ai_score,
            report.get("band"),
            score,
            changed or None,
            f"edited ({len(edited_rationale)} characters)" if edited_rationale else "the system's",
        )
        shown = apply_review(
            score=interview.ai_score,
            rationale=interview.ai_rationale,
            report=report if "rows" in report else None,
            review_score=score,
            review_ratings=changed,
            review_rationale=edited_rationale,
        )
        return {
            "score": shown.score,
            "band": (shown.report or {}).get("band"),
            "reviewed": shown.reviewed or bool(filled),
        }

    async def _latest_panel_decision(self, interview_id: uuid.UUID) -> dict | None:
        """The panel's latest decision on this interview, or None (also None in the seconds of a
        deploy before the table exists)."""

        async def read() -> dict | None:
            row = (
                await self._db.execute(
                    select(InterviewPanelDecision)
                    .where(InterviewPanelDecision.interview_id == interview_id)
                    .order_by(InterviewPanelDecision.decided_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return _panel_decision_out(row) if row is not None else None

        return await tolerate_missing(self._db, read, None)

    async def record_panel_decision(
        self,
        user: User,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
        decision: str,
        rationale: str,
    ) -> dict:
        """Record the hiring panel's decision about a candidate, with its rationale, signed off by the
        person recording it (the client's assessment record).

        A person's decision, never the system's, and it stops at the shortlist. Organization-level
        ownership (decision D2): anyone in the company that owns the job. Only once the interview
        has finished (completed, or ended early). Append-only: a new decision is a new row, and the
        latest is the one shown, so what was decided before is kept."""
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if not can_manage_job(user, job):
            raise PermissionDeniedException("You do not have access to this job")
        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None:
            raise InterviewNotFound()
        if interview.status not in PANEL_DECISION_STATUSES:
            raise ValidationException(
                "The interview has not finished yet, so there is nothing to decide on.",
                code="INTERVIEW_NOT_FINISHED",
            )
        reason = " ".join((rationale or "").split())
        if len(reason) < MIN_RATIONALE_CHARS:
            raise ValidationException(
                "Say why, in a sentence or two, so the decision can be understood later.",
                code="RATIONALE_REQUIRED",
            )
        name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email
        row = InterviewPanelDecision(
            interview_id=interview.id,
            decision=PanelDecision(decision).value,
            rationale=reason,
            decided_by=user.id,
            decided_by_name=name,
            decided_at=datetime.now(UTC),
        )
        self._db.add(row)
        await self._db.commit()
        return _panel_decision_out(row)

    async def _resolve_cv_assessment(
        self, interview: Interview, job: Job
    ) -> tuple[int | None, list[str] | None, list[str] | None, str | None]:
        """The CV assessment for an existing interview's candidate (see
        ``resolve_cv_assessment``)."""
        return await self.resolve_cv_assessment(
            job, interview.talent_pool_profile, interview.application_id
        )

    async def resolve_cv_assessment(
        self, job: Job, profile, application_id: uuid.UUID | None = None
    ) -> tuple[int | None, list[str] | None, list[str] | None, str | None]:
        """Best-effort lookup of this candidate's independently-computed CV fit
        score for this same job, shown alongside the interview assessment.

        Prefers the Application's score when one exists (``Application.ai_score``
        is inherently scoped to one job, so it's always trustworthy). Falls
        back to the talent pool profile's score for sourced-only candidates
        with no Application — but ``TalentPoolProfiles.ai_score`` is a single
        mutable column that gets overwritten whenever that profile is scored
        against *any* job, so it's only trusted here if ``ai_score_job_hash``
        still matches this job's current scoring inputs; otherwise it could
        be showing a stale score computed for a completely different job.
        """
        if application_id:
            application = await self._application_repo.get_by_id(application_id)
            if application and application.ai_score is not None:
                return (
                    application.ai_score,
                    application.ai_strengths,
                    application.ai_weaknesses,
                    application.ai_fit_summary,
                )
            return None, None, None, None

        if not profile or profile.ai_score is None or not profile.ai_score_job_hash:
            return None, None, None, None

        from app.modules.ai.scoring_service import hash_job_scoring_inputs
        from app.modules.jobs.schemas import build_full_description

        description = build_full_description(
            about_the_role=job.about_the_role,
            key_responsibilities=job.key_responsibilities,
            requirements=job.requirements,
            preferred_certifications=job.preferred_certifications,
            technical_competencies=job.technical_competencies,
            what_we_offer=job.what_we_offer,
            legacy_description=job.description,
        )
        current_hash = hash_job_scoring_inputs(
            description, job.required_skills or [], job.seniority_level
        )
        if current_hash != profile.ai_score_job_hash:
            # Stale — this profile was last scored against a different job.
            return None, None, None, None

        return (
            profile.ai_score,
            profile.ai_strengths,
            profile.ai_weaknesses,
            profile.ai_fit_summary,
        )

