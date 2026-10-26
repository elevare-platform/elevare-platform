"""HTTP endpoints for the interviews module."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_candidate, get_db, require_role
from app.core.exceptions import ValidationException
from app.core.limiter import limiter
from app.modules.candidates.models import CandidateProfile
from app.modules.interviews.questions import InterviewQuestionService
from app.modules.interviews.schema import (
    CandidateInterviewDetailResponse,
    CandidateInterviewResponse,
    InterviewCompleteRequest,
    InterviewDetailResponse,
    InterviewInviteBulkSendResponse,
    InterviewInviteByEmailRequest,
    InterviewInviteByEmailResponse,
    InterviewInviteSendResponse,
    InterviewLinkResponse,
    InterviewPricingResponse,
    InterviewPublicInfoResponse,
    InterviewQuestionsDraftRequest,
    InterviewQuestionsDraftResponse,
    InterviewQuestionsPutRequest,
    InterviewQuestionsResponse,
    InterviewReinstateResponse,
    InterviewResetRequestResponse,
    InterviewScoreRequestResponse,
    InterviewSessionResponse,
    InterviewUploadUrlResponse,
    ScoringProfileIn,
    ScoringProfileResponse,
    StrictEventRequest,
    StrictInterviewStateResponse,
    StrictRecordingPartResponse,
    StrictStartRequest,
)
from app.modules.interviews.scoring_profile_service import ScoringProfileService
from app.modules.interviews.service import InterviewService
from app.modules.users.models import User


async def _read_answer_audio(request: Request) -> tuple[bytes, str | None]:
    """The spoken answer sent as the request body, refused as soon as it grows past the limit
    (the Content-Length header can be missing or wrong, so the bytes are counted as they come)."""
    limit = settings.strict_answer_max_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise ValidationException("That recording is too large.", code="INTERVIEW_ANSWER_TOO_LARGE")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise ValidationException(
                "That recording is too large.", code="INTERVIEW_ANSWER_TOO_LARGE"
            )
        chunks.append(chunk)
    return b"".join(chunks), request.headers.get("content-type")


# ─── Authenticated candidate routes — resolved via application_id + login ───

router = APIRouter()


@router.post(
    "/applications/{application_id}/strict/start",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
async def start_strict_interview(
    application_id: uuid.UUID,
    body: StrictStartRequest = StrictStartRequest(),
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """Candidate starts (or resumes, after a reload) their strict interview."""
    service = InterviewService(db)
    try:
        return await service.start_strict(
            application_id=application_id,
            candidate_id=candidate.user_id,
            accepted=body.accepted,
            rules_version=body.rules_version,
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/strict/event",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
async def report_strict_event(
    application_id: uuid.UUID,
    body: StrictEventRequest,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """The screen reports a leave, a return, a key press or a heartbeat. The server times it,
    and the reply says whether it ended the interview and how many warnings are used."""
    service = InterviewService(db)
    try:
        return await service.strict_event(
            application_id=application_id,
            candidate_id=candidate.user_id,
            event_type=body.type,
            cause=body.cause,
            key=body.key,
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/strict/stop",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
async def stop_strict_interview(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """The candidate pressed "I need to stop" and confirmed. Ends the interview as their own
    choice; the employer can reinstate it."""
    service = InterviewService(db)
    try:
        return await service.stop_strict(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/strict/recording-part",
    status_code=201,
    response_model=StrictRecordingPartResponse,
)
async def create_strict_recording_part_url(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> StrictRecordingPartResponse:
    """An upload URL for an earlier recording the browser kept across a reload. The server
    joins it with the final recording into one video before scoring."""
    service = InterviewService(db)
    try:
        return await service.recording_part_url(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/strict/answer",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
async def answer_strict_interview(
    application_id: uuid.UUID,
    request: Request,
    turn_id: uuid.UUID = Query(...),
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """Candidate sends the spoken answer to the question on screen (the request body is the
    audio). The reply is the next question, a follow-up, or the end of the interview."""
    audio, content_type = await _read_answer_audio(request)
    service = InterviewService(db)
    try:
        return await service.answer_strict(
            application_id=application_id,
            candidate_id=candidate.user_id,
            turn_id=turn_id,
            audio=audio,
            content_type=content_type,
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/session",
    status_code=201,
    response_model=InterviewSessionResponse,
)
async def create_interview_session(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionResponse:
    """Candidate starts (or reconnects to) their live AI video interview.

    Returns a short-lived Realtime API client secret — the browser connects
    directly to OpenAI with it, the live audio never passes through our
    servers.
    """
    service = InterviewService(db)
    try:
        return await service.create_session(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/request-reset",
    status_code=200,
    response_model=InterviewResetRequestResponse,
)
async def request_interview_reset(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewResetRequestResponse:
    """Candidate locked out by the restart lock asks the employer to reset it."""
    service = InterviewService(db)
    try:
        return await service.request_reset(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/upload-url",
    status_code=201,
    response_model=InterviewUploadUrlResponse,
)
async def create_upload_url(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> InterviewUploadUrlResponse:
    """Candidate requests a presigned URL to upload their recording directly to R2."""
    service = InterviewService(db)
    try:
        return await service.generate_upload_url(
            application_id=application_id, candidate_id=candidate.user_id
        )
    finally:
        await service.close()


@router.post(
    "/applications/{application_id}/complete",
    status_code=200,
    response_model=CandidateInterviewResponse,
)
async def complete_interview_upload(
    application_id: uuid.UUID,
    body: InterviewCompleteRequest = InterviewCompleteRequest(),
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> CandidateInterviewResponse:
    """Candidate confirms the recording finished uploading to R2."""
    service = InterviewService(db)
    try:
        return await service.complete_upload(
            application_id=application_id,
            candidate_id=candidate.user_id,
            transcript=body.transcript,
            realtime_usage=body.realtime_usage,
        )
    finally:
        await service.close()


@router.get(
    "/applications/{application_id}",
    status_code=200,
    response_model=CandidateInterviewDetailResponse,
)
async def get_interview(
    application_id: uuid.UUID,
    candidate: CandidateProfile = Depends(get_candidate),
    db: AsyncSession = Depends(get_db),
) -> CandidateInterviewDetailResponse:
    """Candidate views the status of their interview for an application. Never the
    employer's assessment of them."""
    service = InterviewService(db)
    try:
        interview = await service.get_for_application(
            application_id=application_id, candidate_id=candidate.user_id
        )
        return CandidateInterviewDetailResponse(
            **CandidateInterviewResponse.model_validate(interview).model_dump(),
            style=await service.style_of(interview),
            started=await service.is_started(interview),
        )
    finally:
        await service.close()

@router.post("/{talent_pool_profile_id}/send-invite", response_model=InterviewInviteSendResponse, status_code=200)
async def send_interview_invite(
    talent_pool_profile_id: uuid.UUID,
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly send (or resend) an AI interview invite to one candidate."""
    service = InterviewService(db)
    try:
        return await service.send_invite(current_user, job_id, talent_pool_profile_id)
    finally:
        await service.close()


@router.post(
    "/jobs/{job_id}/invite-by-email",
    response_model=InterviewInviteByEmailResponse,
    status_code=200,
)
@limiter.limit("60/hour")
async def invite_to_interview_by_email(
    request: Request,
    job_id: uuid.UUID,
    data: InterviewInviteByEmailRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Send a job's AI interview to an email address, with no CV or account needed. The address
    goes on the job's interview list (and stays there if the email could not be sent). Costs
    credits like any invite. Limited to 60 an hour."""
    service = InterviewService(db)
    try:
        return await service.invite_by_email(current_user, job_id, data.email)
    finally:
        await service.close()


@router.post(
    "/{talent_pool_profile_id}/reinstate",
    response_model=InterviewReinstateResponse,
    status_code=200,
)
async def reinstate_interview(
    talent_pool_profile_id: uuid.UUID,
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Let a candidate carry on with an AI interview that ended early, where they stopped.
    Only the company that owns the job may do this. Nothing is charged."""
    service = InterviewService(db)
    try:
        return await service.reinstate(current_user, job_id, talent_pool_profile_id)
    finally:
        await service.close()


@router.get("/pricing", response_model=InterviewPricingResponse, status_code=200)
async def get_interview_pricing(
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """What an AI interview costs the caller's organization, and its credit balance."""
    service = InterviewService(db)
    try:
        return await service.get_pricing(current_user)
    finally:
        await service.close()


@router.get(
    "/jobs/{job_id}/questions", response_model=InterviewQuestionsResponse, status_code=200
)
async def get_job_interview_questions(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """The job's strict-interview questions, in the order a candidate sees them, with the limits.
    Anyone in the company that owns the job."""
    return await InterviewQuestionService(db).list_questions(current_user, job_id)


@router.put(
    "/jobs/{job_id}/questions", response_model=InterviewQuestionsResponse, status_code=200
)
async def save_job_interview_questions(
    job_id: uuid.UUID,
    data: InterviewQuestionsPutRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Save the job's whole list of questions in place of the old one. Every problem is named in
    the refusal (too many, a bad time, times that do not fit the interview). An empty list
    clears the questions."""
    return await InterviewQuestionService(db).replace_questions(
        current_user, job_id, [item.model_dump() for item in data.questions]
    )


@router.post(
    "/jobs/{job_id}/questions/draft",
    response_model=InterviewQuestionsDraftResponse,
    status_code=200,
)
@limiter.limit("20/hour")
async def draft_job_interview_questions(
    request: Request,
    job_id: uuid.UUID,
    data: InterviewQuestionsDraftRequest = InterviewQuestionsDraftRequest(),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Ask the AI to draft questions from the job's interview brief. Nothing is saved: the
    employer reads and edits the draft and saves it. Needs a brief. Limited to 20 an hour, as it
    is a paid AI call."""
    return await InterviewQuestionService(db).draft_questions(current_user, job_id, data.count)


@router.get(
    "/jobs/{job_id}/scoring-profile", response_model=ScoringProfileResponse, status_code=200
)
async def get_job_scoring_profile(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """The job's scoring profile (null when it has none), with the ready-made templates and the
    defaults the editor starts from. Anyone in the company that owns the job."""
    return await ScoringProfileService(db).get(current_user, job_id)


@router.put(
    "/jobs/{job_id}/scoring-profile", response_model=ScoringProfileResponse, status_code=200
)
async def save_job_scoring_profile(
    job_id: uuid.UUID,
    data: ScoringProfileIn,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Save the job's scoring profile: competencies with weights adding up to 100, which are key,
    and the band thresholds. Every problem is named in the refusal. Applies to interviews scored
    from now on; reports already made are not changed. Strict interview only."""
    return await ScoringProfileService(db).save(
        current_user,
        job_id,
        [item.model_dump() for item in data.competencies],
        data.bands.model_dump() if data.bands else None,
        data.key_min_rating,
        data.template_code,
    )


@router.delete(
    "/jobs/{job_id}/scoring-profile", response_model=ScoringProfileResponse, status_code=200
)
async def remove_job_scoring_profile(
    job_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Take the scoring profile off the job, so it is scored by the generic scorecard again."""
    return await ScoringProfileService(db).remove(current_user, job_id)


@router.post("/{talent_pool_profile_id}/interview-link", response_model=InterviewLinkResponse, status_code=200)
async def get_interview_link(
    talent_pool_profile_id: uuid.UUID,
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return the candidate's interview link so the employer can share it
    themselves. Nothing is emailed, and a link already in use is not changed."""
    service = InterviewService(db)
    try:
        return await service.get_interview_link(current_user, job_id, talent_pool_profile_id)
    finally:
        await service.close()


@router.post("/send-invites", response_model=InterviewInviteBulkSendResponse, status_code=200)
async def send_interview_invites_to_all(
    job_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly send (or resend) AI interview invites to everyone on this job's interview list."""
    service = InterviewService(db)
    try:
        return await service.send_invites_to_all(current_user, job_id)
    finally:
        await service.close()


@router.post("/score", response_model=InterviewScoreRequestResponse, status_code=202)
async def request_interview_scoring(
    job_id: uuid.UUID = Query(...),
    talent_pool_profile_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Score a finished interview that has no AI score yet (for example one taken
    on the Starter plan). Runs in the background; the interview detail shows the
    score when it is ready."""
    service = InterviewService(db)
    try:
        return await service.request_scoring(
            current_user, job_id, talent_pool_profile_id
        )
    finally:
        await service.close()


@router.get("/detail", response_model=InterviewDetailResponse, status_code=200)
async def get_interview_detail(
    job_id: uuid.UUID = Query(...),
    talent_pool_profile_id: uuid.UUID = Query(...),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Employer views transcript/score/video for one candidate's completed interview."""
    service = InterviewService(db)
    try:
        return await service.get_detail_for_employer(
            current_user, job_id, talent_pool_profile_id
        )
    finally:
        await service.close()


@router.get("/costs", status_code=200)
async def get_interview_costs(
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return the current month's interview cost summary, broken down by
    component (realtime/transcription/scoring). Admin only."""
    service = InterviewService(db)
    try:
        return await service.get_monthly_cost_summary()
    finally:
        await service.close()


@router.get("/costs/trend", status_code=200)
async def get_interview_costs_trend(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return a monthly interview cost/call trend, broken down by component,
    optionally bounded by ?from=&to= (YYYY-MM-DD). Omit both for the full
    history. Admin only."""
    service = InterviewService(db)
    try:
        return await service.get_cost_trend(from_date, to_date)
    finally:
        await service.close()


# ─── Public token routes — no login required, reached from an emailed link ──
#
# Being added to a job's interview list is what grants access, not having
# an Elevare account — sourced/parsed profiles reach these from an emailed
# magic link instead of a Bearer token.

public_router = APIRouter()


@public_router.get(
    "/{token}",
    status_code=200,
    response_model=InterviewPublicInfoResponse,
)
@limiter.limit("30/minute")
async def get_interview_invite_info(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewPublicInfoResponse:
    """Job/company context for the consent screen, before the candidate starts."""
    service = InterviewService(db)
    try:
        return await service.get_public_info(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/session",
    status_code=201,
    response_model=InterviewSessionResponse,
)
@limiter.limit("10/minute")
async def create_interview_session_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewSessionResponse:
    """Start (or reconnect to) the live AI video interview from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.create_session_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/strict/start",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
@limiter.limit("20/minute")
async def start_strict_interview_by_token(
    request: Request,
    token: str,
    body: StrictStartRequest = StrictStartRequest(),
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """Start (or resume, after a reload) the strict interview from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.start_strict_by_token(
            token, accepted=body.accepted, rules_version=body.rules_version
        )
    finally:
        await service.close()


@public_router.post(
    "/{token}/strict/event",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
@limiter.limit("120/minute")
async def report_strict_event_by_token(
    request: Request,
    token: str,
    body: StrictEventRequest,
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """The screen reports a leave, a return, a key press or a heartbeat (about 4 a minute)."""
    service = InterviewService(db)
    try:
        return await service.strict_event_by_token(
            token, event_type=body.type, cause=body.cause, key=body.key
        )
    finally:
        await service.close()


@public_router.post(
    "/{token}/strict/stop",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
@limiter.limit("10/minute")
async def stop_strict_interview_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """The candidate pressed "I need to stop" and confirmed."""
    service = InterviewService(db)
    try:
        return await service.stop_strict_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/strict/recording-part",
    status_code=201,
    response_model=StrictRecordingPartResponse,
)
@limiter.limit("20/minute")
async def create_strict_recording_part_url_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> StrictRecordingPartResponse:
    """An upload URL for an earlier recording the browser kept across a reload."""
    service = InterviewService(db)
    try:
        return await service.recording_part_url_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/strict/answer",
    status_code=200,
    response_model=StrictInterviewStateResponse,
)
@limiter.limit("30/minute")
async def answer_strict_interview_by_token(
    request: Request,
    token: str,
    turn_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
) -> StrictInterviewStateResponse:
    """Send the spoken answer to the question on screen (the request body is the audio)."""
    audio, content_type = await _read_answer_audio(request)
    service = InterviewService(db)
    try:
        return await service.answer_strict_by_token(
            token, turn_id=turn_id, audio=audio, content_type=content_type
        )
    finally:
        await service.close()


@public_router.post(
    "/{token}/request-reset",
    status_code=200,
    response_model=InterviewResetRequestResponse,
)
@limiter.limit("5/minute")
async def request_interview_reset_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewResetRequestResponse:
    """No-login candidate locked out by the restart lock asks the employer to reset it."""
    service = InterviewService(db)
    try:
        return await service.request_reset_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/upload-url",
    status_code=201,
    response_model=InterviewUploadUrlResponse,
)
@limiter.limit("10/minute")
async def create_upload_url_by_token(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InterviewUploadUrlResponse:
    """Request a presigned upload URL from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.generate_upload_url_by_token(token)
    finally:
        await service.close()


@public_router.post(
    "/{token}/complete",
    status_code=200,
    response_model=CandidateInterviewResponse,
)
@limiter.limit("10/minute")
async def complete_interview_upload_by_token(
    request: Request,
    token: str,
    body: InterviewCompleteRequest = InterviewCompleteRequest(),
    db: AsyncSession = Depends(get_db),
) -> CandidateInterviewResponse:
    """Confirm the recording finished uploading, from an emailed invite link."""
    service = InterviewService(db)
    try:
        return await service.complete_upload_by_token(
            token, transcript=body.transcript, realtime_usage=body.realtime_usage
        )
    finally:
        await service.close()
