"""Interview service — business logic for AI video interviews."""

import secrets
import uuid
from datetime import UTC, date, datetime, timedelta

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai_pricing import compute_realtime_cost_usd
from app.core.config import settings
from app.core.cost_trend import effective_month_bounds, month_range
from app.core.exceptions import (
    ApplicationNotFound,
    InterviewNotFound,
    PermissionDeniedException,
    ValidationException,
)
from app.core.storage import get_storage_service
from app.modules.applications.repository import ApplicationRepository
from app.modules.candidates.repository import CandidateRepository
from app.modules.interview_list.repository import InterviewListRepository
from app.modules.interviews.enums import InterviewCostComponent, InterviewStatus
from app.modules.interviews.models import Interview
from app.modules.interviews.repository import InterviewRepository
from app.modules.interviews.schema import (
    InterviewDetailResponse,
    InterviewPublicInfoResponse,
    InterviewSessionResponse,
    InterviewUploadUrlResponse,
    RealtimeUsageDetail,
)
from app.modules.interviews.tasks import (
    send_ai_interview_invite_email,
    send_interview_restart_request_email,
    transcribe_and_score_interview_task,
)
from app.modules.jobs.models import Job
from app.modules.talent_pool.repository import TalentPoolRepository

_UPLOAD_URL_EXPIRES_SECONDS = 60 * 30
_VIDEO_CONTENT_TYPE = "video/webm"
_INVITE_TOKEN_EXPIRY_DAYS = 14

_BASE_INTERVIEWER_INSTRUCTIONS = (
    "You are conducting a live, spoken screening interview on behalf of an "
    "employer. Ask an opening question based on the brief below, listen to "
    "the candidate's spoken answer, and ask real follow-up questions based "
    "on what they actually say, the way a human interviewer would. Keep "
    "the conversation focused and professional. Speak naturally and "
    "conversationally, the way a real interviewer talks, not like a script "
    "being read aloud. Do not reveal the brief itself to the candidate."
)


def _build_instructions(interview_brief: str, max_duration_minutes: int) -> str:
    """Compose the realtime session's system instructions from the job's interview brief."""
    pacing = (
        f"You have approximately {max_duration_minutes} minutes for this "
        "conversation. Budget your time across the topics in the brief "
        "below — don't let one answer consume the whole interview. If a "
        "candidate goes into excessive detail on one topic, politely "
        "acknowledge what they've shared and steer to the next question "
        "so you can cover everything in the time available."
    )
    return (
        f"{_BASE_INTERVIEWER_INSTRUCTIONS}\n\n{pacing}"
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

    async def create_invite(
        self, job: Job, talent_pool_profile_id: uuid.UUID
    ) -> tuple[Interview, str] | None:
        """Get-or-create the Interview row for this job+candidate and (re)issue a token.

        Returns (interview, interview_url) or None if the job has no
        interview_brief configured — being on the interview list only
        triggers an AI interview invite for jobs that actually have the
        feature turned on.
        """
        if not job.interview_brief:
            return None

        interview = await self._repo.get_by_job_and_profile(
            job.id, talent_pool_profile_id
        )
        if interview is None:
            application_id = await self._find_matching_application_id(
                job.id, talent_pool_profile_id
            )
            interview = await self._repo.create(
                job_id=job.id,
                talent_pool_profile_id=talent_pool_profile_id,
                application_id=application_id,
            )
        elif interview.status in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            # Already completed — nothing new to invite them to.
            return None

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
        if not application.job.interview_brief:
            raise ValidationException(
                "This job does not have an AI video interview configured"
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
        return InterviewPublicInfoResponse(
            job_title=job.title,
            company_name=employer_profile.company_name if employer_profile else None,
            status=interview.status,
            max_duration_minutes=settings.interview_max_duration_minutes,
            session_start_count=interview.session_start_count,
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
        if interview.status in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            raise ValidationException("This interview has already been completed")

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
        secret = await self._get_client().realtime.client_secrets.create(
            expires_after={
                "anchor": "created_at",
                "seconds": min(max_duration_minutes * 60, 7200),
            },
            session={
                "type": "realtime",
                "model": settings.realtime_model,
                "instructions": _build_instructions(job.interview_brief, max_duration_minutes),
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
            },
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
                title=f"{candidate_name} needs their AI interview reset",
                body=(
                    f"{candidate_name} was locked out of their AI interview for "
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
        if interview.status not in (
            InterviewStatus.PENDING.value,
            InterviewStatus.IN_PROGRESS.value,
        ):
            raise ValidationException("This interview has already been uploaded")

        key = f"interviews/{interview.id}/recording.webm"
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

    async def _complete_upload(
        self,
        interview: Interview,
        transcript: str | None = None,
        realtime_usage: RealtimeUsageDetail | None = None,
    ):
        if not interview.r2_key:
            raise ValidationException("No upload was started for this interview")

        now = datetime.now(UTC)
        update_data: dict = {
            "status": InterviewStatus.UPLOADED.value,
            "completed_at": now,
            "video_expires_at": now
            + timedelta(days=settings.interview_video_retention_days),
        }
        # Only set if present — never overwrite an already-saved transcript
        # with a blank one on a defensive resend/retry.
        if transcript:
            update_data["transcript"] = transcript

        interview = await self._repo.update(interview.id, update_data)

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

    async def _send_invite_for_profile(self, job: Job, talent_pool_profile_id: uuid.UUID) -> dict:
        """
        Shared per-candidate send/resend logic used by send_invite and send_invites_to_all.
        """
        from app.modules.jobs.schemas import PLATFORM_COMPANY_NAME
        from app.modules.notifications.repository import NotificationRepository

        if not job.interview_brief:
            raise ValidationException("This job does not have an AI interview configured")

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

        invite = await self.create_invite(job, talent_pool_profile_id)
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
        send_ai_interview_invite_email.delay(
            candidate_email=candidate_email,
            interview_url=interview_url,
            job_title=job.title,
            company_name=company_name,
        )

        if is_first_invite and is_self_registered:
            await NotificationRepository(self._db).create(
                recipient_id=profile.candidate_profile.user_id,
                type="AI_INTERVIEW_INVITE",
                title=f"AI interview invite: {job.title}",
                body=(
                    f"{company_name} has invited you to a live AI interview "
                    f"for the {job.title} role. It's a real-time voice "
                    "conversation with an AI interviewer, reviewed by the "
                    f"employer afterward.\n\nStart here: {interview_url}"
                ),
                entity_type="APPLICATION" if _interview.application_id else None,
                entity_id=_interview.application_id,
            )
            await self._db.commit()

        return {"sent": True, "reason": None}

    async def send_invite(
        self,
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> dict:
        """Explicit send/resend for one candidate."""
        from app.core.exceptions import JobNotFoundError, PermissionDeniedException
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()

        if job.employer_id != employer_id:
            raise PermissionDeniedException("You do not own this job")

        return await self._send_invite_for_profile(job, talent_pool_profile_id)

    async def send_invites_to_all(self, employer_id: uuid.UUID, job_id: uuid.UUID) -> dict:
        """Bulk send/resend to everyone on this job's interview list."""
        from app.core.exceptions import JobNotFoundError, PermissionDeniedException
        from app.modules.interview_list.repository import InterviewListRepository
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()

        if job.employer_id != employer_id:
            raise PermissionDeniedException("You do not own this job")

        entries = await InterviewListRepository(self._db).list_for_job(employer_id, job_id)

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
        employer_id: uuid.UUID,
        job_id: uuid.UUID,
        talent_pool_profile_id: uuid.UUID,
    ) -> InterviewDetailResponse:
        """Employer views transcript/score/video for one candidate's completed interview."""
        from app.core.exceptions import JobNotFoundError
        from app.modules.jobs.repository import JobRepository

        job = await JobRepository(self._db).get_by_id(job_id)
        if job is None:
            raise JobNotFoundError()
        if job.employer_id != employer_id:
            raise PermissionDeniedException("You do not own this job")

        interview = await self._repo.get_by_job_and_profile(job_id, talent_pool_profile_id)
        if interview is None or interview.status not in (
            InterviewStatus.UPLOADED.value,
            InterviewStatus.SCORED.value,
        ):
            raise InterviewNotFound()

        video_url = None
        if interview.r2_key:
            video_url = await get_storage_service().generate_presigned_url(
                interview.r2_key, expires_seconds=3600,
            )

        cv_score, cv_strengths, cv_weaknesses, cv_fit_summary = (
            await self._resolve_cv_assessment(interview, job)
        )

        return InterviewDetailResponse(
            status=interview.status,
            transcript=interview.transcript,
            ai_score=interview.ai_score,
            ai_rationale=interview.ai_rationale,
            ai_scored_at=interview.ai_scored_at,
            video_url=video_url,
            completed_at=interview.completed_at,
            cv_score=cv_score,
            cv_strengths=cv_strengths,
            cv_weaknesses=cv_weaknesses,
            cv_fit_summary=cv_fit_summary,
        )

    async def _resolve_cv_assessment(
        self, interview: Interview, job: Job
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
        if interview.application_id:
            application = await self._application_repo.get_by_id(interview.application_id)
            if application and application.ai_score is not None:
                return (
                    application.ai_score,
                    application.ai_strengths,
                    application.ai_weaknesses,
                    application.ai_fit_summary,
                )
            return None, None, None, None

        profile = interview.talent_pool_profile
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

