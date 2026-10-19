"""Rescoring a job's candidates who have no usable score.

A candidate has no usable score when their CV could not be read, when scoring failed,
or (older data) when a failure was saved as a score of 0. Rescore puts them back in the
queue: a CV that could not be read is read again from the stored file, a readable one is
just scored again, and a candidate with a real score is never touched."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.core.exceptions import (
    NotFoundException,
    PermissionDeniedException,
    PlatformError,
    ValidationException,
)
from app.modules.ai import tasks as ai_tasks
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.ai.scoring_outcome import CV_UNREADABLE, SCORING_FAILED
from app.modules.candidates.models import CandidateCvs
from app.modules.rescore import service as rescore_service
from app.modules.rescore.schemas import RescoreRequest
from app.modules.rescore.service import RescoreService
from tests.ai.test_scoring_failure import READABLE, UNREADABLE
from tests.conftest import (
    make_admin,
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)
from tests.interviews.conftest import (
    make_application,
    make_candidate_profile,
    make_candidate_user,
    make_talent_pool_profile,
)

COMPLETED = CVParsingStatus.COMPLETED.value
FAILED = CVParsingStatus.FAILED.value
PENDING = CVParsingStatus.PENDING.value
FLAGGED = CVParsingStatus.FLAGGED.value


@pytest.fixture
def queued(monkeypatch):
    """Stand-ins for the three Celery tasks, so nothing runs and calls can be checked."""
    calls = MagicMock()
    monkeypatch.setattr(ai_tasks.score_application_task, "delay", calls.application)
    monkeypatch.setattr(ai_tasks.score_talent_pool_profile_task, "delay", calls.pool)
    monkeypatch.setattr(ai_tasks.run_full_pipeline_task, "delay", calls.pipeline)
    return calls


async def employer_with_job(db_session, professional=True):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    if professional:
        await make_subscription_for(db_session, organization)
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    return employer, job


async def submission(
    db_session,
    parsed_data=READABLE,
    parse_status=COMPLETED,
    r2_key="cvs/cv.pdf",
):
    row = ParsedCVSubmission(
        filename="cv.pdf",
        parse_status=parse_status,
        parsed_data=parsed_data,
        r2_key=r2_key,
        cv_text_hash=uuid.uuid4().hex,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def application_for(db_session, job, sub=None, **row):
    """An application on `job` whose CV is `sub` (a readable CV when not given)."""
    user = make_candidate_user()
    db_session.add(user)
    await db_session.flush()
    candidate = await make_candidate_profile(db_session, user)
    sub = sub or await submission(db_session)
    cv = CandidateCvs(
        candidate_id=candidate.id, key="cv.pdf", filename="cv.pdf", submission_id=sub.id
    )
    db_session.add(cv)
    await db_session.flush()
    return await make_application(db_session, user.id, job.id, cv_id=cv.id, **row)


async def profile_for(db_session, employer, job, sub=None, **row):
    sub = sub or await submission(db_session)
    return await make_talent_pool_profile(
        db_session,
        employer.id,
        parsed_submission_id=sub.id,
        sourced_for_job_id=job.id,
        **row,
    )


async def grow_old(db_session, row, hours=3):
    row.updated_at = datetime.now(UTC) - timedelta(hours=hours)
    await db_session.flush()


REAL = {
    "ai_score": 72,
    "ai_fit_summary": "A strong fit.",
    "ai_strengths": ["Sales leadership"],
    "ai_weaknesses": [],
    "ai_score_job_hash": "job-hash",
    "ai_score_cv_hash": "cv-hash",
}


def is_reset(row):
    return (
        row.ai_score is None
        and row.ai_score_failure is None
        and row.ai_fit_summary is None
        and row.ai_score_job_hash is None
        and row.ai_score_cv_hash is None
        and row.ai_score_computed_at is None
    )


# --- who needs it ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_counts_the_candidates_with_no_usable_score_and_nobody_else(db_session):
    employer, job = await employer_with_job(db_session)
    _, other_job = await employer_with_job(db_session)
    # They need it:
    await application_for(db_session, job, ai_score_failure=CV_UNREADABLE)
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)
    await application_for(db_session, job, ai_score=0, ai_fit_summary=None)  # an old fake 0
    forgotten = await application_for(db_session, job)  # unscored for hours
    await grow_old(db_session, forgotten)
    await profile_for(db_session, employer, job, ai_score_failure=CV_UNREADABLE)
    # They do not:
    await application_for(db_session, job, **REAL)  # a real score
    await application_for(db_session, job, ai_score=0, ai_fit_summary="Genuinely poor fit.")
    await application_for(db_session, job)  # waiting, just applied
    await application_for(db_session, job, status="WITHDRAWN", ai_score_failure=SCORING_FAILED)
    await application_for(db_session, other_job, ai_score_failure=SCORING_FAILED)
    await profile_for(db_session, employer, job, **REAL)
    await profile_for(db_session, employer, other_job, ai_score_failure=SCORING_FAILED)

    status = await RescoreService(db_session).status(employer, job.id)

    assert (status.applications, status.pipeline, status.total) == (4, 1, 5)


# --- what it does ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_readable_cv_whose_scoring_failed_is_just_scored_again(db_session, queued):
    employer, job = await employer_with_job(db_session)
    application = await application_for(
        db_session, job, ai_score_failure=SCORING_FAILED, ai_score_job_hash="stale"
    )

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert (result.scoring, result.reparsing, result.remaining) == (1, 0, 0)
    queued.application.assert_called_once_with(str(application.id))
    queued.pipeline.assert_not_called()
    assert is_reset(application)


@pytest.mark.asyncio
async def test_a_cv_that_could_not_be_read_is_read_again_from_the_stored_file(
    db_session, queued
):
    employer, job = await employer_with_job(db_session)
    sub = await submission(db_session, parsed_data=UNREADABLE, parse_status=FLAGGED, r2_key="cvs/a.pdf")
    sub.flag_reasons = ["Could not read this CV"]
    application = await application_for(db_session, job, sub, ai_score_failure=CV_UNREADABLE)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert (result.scoring, result.reparsing) == (0, 1)
    queued.pipeline.assert_called_once_with(
        submission_id=str(sub.id), cache_key=f"cv_parse:{sub.cv_text_hash}", r2_key="cvs/a.pdf"
    )
    # Scoring follows when the read finishes (the pipeline queues it), not before.
    queued.application.assert_not_called()
    await db_session.refresh(sub)
    assert sub.parse_status == PENDING
    assert sub.parsed_data is None and sub.flag_reasons is None
    assert is_reset(application)


@pytest.mark.asyncio
async def test_a_parse_that_failed_outright_is_read_again_too(db_session, queued):
    employer, job = await employer_with_job(db_session)
    sub = await submission(db_session, parsed_data=None, parse_status=FAILED)
    sub.error_message = "timeout"
    await application_for(db_session, job, sub, ai_score_failure=CV_UNREADABLE)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert result.reparsing == 1
    await db_session.refresh(sub)
    assert (sub.parse_status, sub.error_message) == (PENDING, None)


@pytest.mark.asyncio
async def test_a_file_shared_by_several_candidates_is_read_once(db_session, queued):
    employer, job = await employer_with_job(db_session)
    sub = await submission(db_session, parsed_data=UNREADABLE, parse_status=FLAGGED)
    first = await application_for(db_session, job, sub, ai_score_failure=CV_UNREADABLE)
    second = await application_for(db_session, job, sub, ai_score_failure=CV_UNREADABLE)
    pooled = await profile_for(db_session, employer, job, sub, ai_score_failure=CV_UNREADABLE)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert result.reparsing == 3
    assert queued.pipeline.call_count == 1
    assert all(is_reset(row) for row in (first, second, pooled))


@pytest.mark.asyncio
async def test_a_pipeline_profile_is_rescored_against_the_job(db_session, queued):
    employer, job = await employer_with_job(db_session)
    profile = await profile_for(db_session, employer, job, ai_score_failure=SCORING_FAILED)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert result.scoring == 1
    queued.pool.assert_called_once_with(str(profile.id), str(job.id))
    assert is_reset(profile)


@pytest.mark.asyncio
async def test_an_old_fake_zero_is_cleared_so_it_is_not_skipped_as_already_scored(
    db_session, queued
):
    employer, job = await employer_with_job(db_session)
    application = await application_for(
        db_session, job, ai_score=0, ai_fit_summary=None,
        ai_score_job_hash="job-hash", ai_score_cv_hash="cv-hash",
    )

    await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert is_reset(application)
    queued.application.assert_called_once_with(str(application.id))


# --- what it leaves alone -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_real_score_is_never_touched(db_session, queued):
    employer, job = await employer_with_job(db_session)
    scored = await application_for(db_session, job, **REAL)
    pooled = await profile_for(db_session, employer, job, **REAL)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert (result.scoring, result.reparsing, result.remaining) == (0, 0, 0)
    queued.application.assert_not_called()
    assert scored.ai_score == 72 and scored.ai_score_job_hash == "job-hash"
    assert pooled.ai_score == 72


@pytest.mark.asyncio
async def test_a_real_score_is_refused_even_when_named_directly(db_session, queued):
    employer, job = await employer_with_job(db_session)
    scored = await application_for(db_session, job, **REAL)

    with pytest.raises(ValidationException):
        await RescoreService(db_session).rescore(
            employer, job.id, RescoreRequest(application_id=scored.id)
        )

    assert scored.ai_score == 72
    queued.application.assert_not_called()


@pytest.mark.asyncio
async def test_a_cv_still_being_read_is_left_alone(db_session, queued):
    employer, job = await employer_with_job(db_session)
    sub = await submission(db_session, parsed_data=None, parse_status=PENDING)
    application = await application_for(db_session, job, sub, ai_score_failure=SCORING_FAILED)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert (result.scoring, result.reparsing, result.in_progress) == (0, 0, 1)
    queued.application.assert_not_called()
    queued.pipeline.assert_not_called()
    assert application.ai_score_failure == SCORING_FAILED


@pytest.mark.asyncio
async def test_an_unreadable_cv_with_no_stored_file_needs_a_new_upload(db_session, queued):
    employer, job = await employer_with_job(db_session)
    sub = await submission(db_session, parsed_data=UNREADABLE, parse_status=FLAGGED, r2_key=None)
    application = await application_for(db_session, job, sub, ai_score_failure=CV_UNREADABLE)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert (result.reparsing, result.no_stored_file) == (0, 1)
    queued.pipeline.assert_not_called()
    assert application.ai_score_failure == CV_UNREADABLE


@pytest.mark.asyncio
async def test_candidates_that_cannot_be_helped_do_not_block_the_ones_behind_them(
    db_session, queued, monkeypatch
):
    monkeypatch.setattr(rescore_service, "RESCORE_BATCH", 2)
    employer, job = await employer_with_job(db_session)
    no_file = await submission(db_session, parsed_data=UNREADABLE, parse_status=FLAGGED, r2_key=None)
    for _ in range(3):
        stuck = await application_for(db_session, job, no_file, ai_score_failure=CV_UNREADABLE)
        await grow_old(db_session, stuck, hours=48)  # the oldest, so first in line
    fixable = await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert result.scoring == 1
    queued.application.assert_called_once_with(str(fixable.id))


# --- one batch at a time --------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_press_starts_one_batch_and_says_how_many_are_left(
    db_session, queued, monkeypatch
):
    monkeypatch.setattr(rescore_service, "RESCORE_BATCH", 2)
    employer, job = await employer_with_job(db_session)
    for _ in range(5):
        await application_for(db_session, job, ai_score_failure=SCORING_FAILED)
    service = RescoreService(db_session)

    first = await service.rescore(employer, job.id, RescoreRequest())
    second = await service.rescore(employer, job.id, RescoreRequest())
    third = await service.rescore(employer, job.id, RescoreRequest())

    assert [(r.scoring, r.remaining) for r in (first, second, third)] == [(2, 3), (2, 1), (1, 0)]
    assert queued.application.call_count == 5


@pytest.mark.asyncio
async def test_pressing_twice_does_not_queue_the_same_candidate_twice(db_session, queued):
    employer, job = await employer_with_job(db_session)
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)
    service = RescoreService(db_session)

    await service.rescore(employer, job.id, RescoreRequest())
    again = await service.rescore(employer, job.id, RescoreRequest())

    assert again.scoring == 0
    assert queued.application.call_count == 1
    assert (await service.status(employer, job.id)).total == 0


# --- one candidate --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_one_candidate_can_be_rescored_by_name(db_session, queued):
    employer, job = await employer_with_job(db_session)
    chosen = await application_for(db_session, job, ai_score_failure=SCORING_FAILED)
    other = await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    result = await RescoreService(db_session).rescore(
        employer, job.id, RescoreRequest(application_id=chosen.id)
    )

    assert result.scoring == 1
    queued.application.assert_called_once_with(str(chosen.id))
    assert other.ai_score_failure == SCORING_FAILED


@pytest.mark.asyncio
async def test_a_candidate_from_another_job_cannot_be_named(db_session, queued):
    employer, job = await employer_with_job(db_session)
    _, elsewhere = await employer_with_job(db_session)
    stranger = await application_for(db_session, elsewhere, ai_score_failure=SCORING_FAILED)

    with pytest.raises(NotFoundException):
        await RescoreService(db_session).rescore(
            employer, job.id, RescoreRequest(application_id=stranger.id)
        )

    assert stranger.ai_score_failure == SCORING_FAILED
    queued.application.assert_not_called()


# --- who may ask ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_someone_from_another_organization_is_refused(db_session, queued):
    _, job = await employer_with_job(db_session)
    outsider, _ = await employer_with_job(db_session)
    victim = await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    with pytest.raises(PermissionDeniedException):
        await RescoreService(db_session).rescore(outsider, job.id, RescoreRequest())
    with pytest.raises(PermissionDeniedException):
        await RescoreService(db_session).status(outsider, job.id)

    assert victim.ai_score_failure == SCORING_FAILED
    queued.application.assert_not_called()


@pytest.mark.asyncio
async def test_a_teammate_in_the_same_organization_may_rescore(db_session, queued):
    from app.modules.employer.enums import OrganizationRole

    owner, job = await employer_with_job(db_session)
    teammate = make_employer()
    teammate.organization_id = owner.organization_id
    teammate.organization_role = OrganizationRole.MEMBER.value
    db_session.add(teammate)
    await db_session.flush()
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    result = await RescoreService(db_session).rescore(teammate, job.id, RescoreRequest())

    assert result.scoring == 1


@pytest.mark.asyncio
async def test_the_starter_plan_is_asked_to_upgrade_and_nothing_is_changed(db_session, queued):
    employer, job = await employer_with_job(db_session, professional=False)
    application = await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    with pytest.raises(PlatformError) as error:
        await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert error.value.code == "PLAN_UPGRADE_REQUIRED"
    assert application.ai_score_failure == SCORING_FAILED
    queued.application.assert_not_called()


@pytest.mark.asyncio
async def test_an_elevare_admin_may_rescore_a_clients_job_on_any_plan(db_session, queued):
    _, job = await employer_with_job(db_session, professional=False)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    result = await RescoreService(db_session).rescore(admin, job.id, RescoreRequest())

    assert result.scoring == 1


# --- when queueing fails --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_candidate_that_could_not_be_queued_says_scoring_failed(db_session, monkeypatch):
    employer, job = await employer_with_job(db_session)
    # Readable CV, so it is only scored again; it starts out marked as an unreadable one.
    application = await application_for(db_session, job, ai_score_failure=CV_UNREADABLE)
    monkeypatch.setattr(
        ai_tasks.score_application_task, "delay", MagicMock(side_effect=RuntimeError("broker down"))
    )

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    # Not left as a silent "waiting": it is marked so it can be tried again.
    assert result.scoring == 0
    assert application.ai_score_failure == SCORING_FAILED
    assert result.remaining == 1


@pytest.mark.asyncio
async def test_a_file_that_could_not_be_queued_marks_its_candidates(db_session, monkeypatch):
    employer, job = await employer_with_job(db_session)
    sub = await submission(db_session, parsed_data=UNREADABLE, parse_status=FLAGGED)
    application = await application_for(db_session, job, sub, ai_score_failure=CV_UNREADABLE)
    monkeypatch.setattr(
        ai_tasks.run_full_pipeline_task, "delay", MagicMock(side_effect=RuntimeError("broker down"))
    )

    result = await RescoreService(db_session).rescore(employer, job.id, RescoreRequest())

    assert result.reparsing == 0
    assert application.ai_score_failure == SCORING_FAILED
