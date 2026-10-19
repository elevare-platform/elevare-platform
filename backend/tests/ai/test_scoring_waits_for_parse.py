"""Scoring waits for a CV that is still being read, instead of skipping it for good.

A candidate who applies right after uploading their CV (or an employer who uploads a CV
with a job attached) queues scoring while the CV is still being parsed. The application
task used to find no parsed data, log "Skipping" and return: that application was never
scored and nothing said why. The talent pool task already waited; both now do the same:
poll every 30 seconds for up to 10 tries, then say scoring failed (never a silent blank),
and the pipeline queues scoring itself as soon as it finishes."""

from unittest.mock import MagicMock

import pytest
from celery.exceptions import Retry
from sqlalchemy import select

from app.core.cv_pipeline.layer7_llm import LLMExtractionResult
from app.modules.ai import tasks as ai_tasks
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.ai.scoring_outcome import SCORING_FAILED
from app.modules.candidates.models import CandidateCvs
from tests.conftest import make_employer, make_job
from tests.interviews.conftest import (
    make_application,
    make_candidate_profile,
    make_candidate_user,
)

from .test_cv_parsing_cost import _run_pipeline_with_llm_result
from .test_scoring_failure import (  # noqa: F401  (task_environment is an autouse fixture)
    GOOD,
    READABLE,
    FakeAI,
    application_case,
    assert_unscored,
    talent_pool_case,
    task_environment,
    use_ai,
)

PENDING = CVParsingStatus.PENDING.value
PROCESSING = CVParsingStatus.PROCESSING.value
COMPLETED = CVParsingStatus.COMPLETED.value

BUILD = {"talent_pool": talent_pool_case, "application": application_case}
KINDS = pytest.mark.parametrize("kind", ["talent_pool", "application"])


def runner(kind, row):
    """Run the real scoring body for this row, with the retry settings passed through."""
    if kind == "talent_pool":
        return lambda **kw: ai_tasks._score_talent_pool_profile_async(
            str(row.id), str(row.sourced_for_job_id), **kw
        )
    return lambda **kw: ai_tasks._score_application_async(str(row.id), **kw)


async def submission_of(db_session, kind, row) -> ParsedCVSubmission:
    if kind == "talent_pool":
        submission_id = row.parsed_submission_id
    else:
        cv = (
            await db_session.execute(
                select(CandidateCvs).where(CandidateCvs.id == row.cv_id)
            )
        ).scalar_one()
        submission_id = cv.submission_id
    return (
        await db_session.execute(
            select(ParsedCVSubmission).where(ParsedCVSubmission.id == submission_id)
        )
    ).scalar_one()


# --- the scoring body ------------------------------------------------------------------


@KINDS
@pytest.mark.parametrize("status", [PENDING, PROCESSING])
@pytest.mark.asyncio
async def test_a_cv_still_being_read_is_waited_for_not_skipped(
    db_session, monkeypatch, kind, status
):
    row, _, _ = await BUILD[kind](db_session, None, parse_status=status)
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    with pytest.raises(ai_tasks._ParsingInProgress):
        await runner(kind, row)()

    await db_session.refresh(row)
    assert ai.calls == 0
    assert row.ai_score is None
    assert row.ai_score_failure is None  # not failed yet: just not ready


@KINDS
@pytest.mark.asyncio
async def test_it_gives_up_after_the_last_try_and_says_scoring_failed(
    db_session, monkeypatch, kind
):
    row, _, _ = await BUILD[kind](db_session, None, parse_status=PENDING)
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await runner(kind, row)(final_attempt=True)

    await db_session.refresh(row)
    assert ai.calls == 0
    assert_unscored(row, SCORING_FAILED)


@KINDS
@pytest.mark.asyncio
async def test_once_the_parse_finishes_the_next_try_scores_it(
    db_session, monkeypatch, kind
):
    row, _, _ = await BUILD[kind](db_session, None, parse_status=PENDING)
    ai = use_ai(monkeypatch, FakeAI(GOOD))
    with pytest.raises(ai_tasks._ParsingInProgress):
        await runner(kind, row)()

    submission = await submission_of(db_session, kind, row)
    submission.parsed_data = READABLE
    submission.parse_status = COMPLETED
    await db_session.flush()
    await runner(kind, row)()

    await db_session.refresh(row)
    assert ai.calls == 1
    assert row.ai_score == GOOD.score
    assert row.ai_score_failure is None


@KINDS
@pytest.mark.asyncio
async def test_a_cv_that_could_not_be_read_at_all_still_says_so(
    db_session, monkeypatch, kind
):
    """FAILED is final, not 'still being read': no waiting, an unreadable marker."""
    row, _, _ = await BUILD[kind](
        db_session, None, parse_status=CVParsingStatus.FAILED.value
    )
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await runner(kind, row)()

    await db_session.refresh(row)
    assert ai.calls == 0
    assert row.ai_score_failure == "CV_UNREADABLE"


# --- the Celery tasks around it --------------------------------------------------------

TASKS = [
    (ai_tasks.score_application_task, "_score_application_async"),
    (ai_tasks.score_talent_pool_profile_task, "_score_talent_pool_profile_async"),
]


@pytest.mark.parametrize("task,body", TASKS, ids=["application", "talent_pool"])
def test_the_task_polls_every_30_seconds_for_up_to_10_tries(monkeypatch, task, body):
    async def waiting(*args, **kwargs):
        raise ai_tasks._ParsingInProgress("still being read")

    retry = MagicMock(side_effect=Retry())
    monkeypatch.setattr(ai_tasks, body, waiting)
    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(Retry):
        task.run("00000000-0000-0000-0000-000000000001")

    assert retry.call_args.kwargs["countdown"] == 30
    assert retry.call_args.kwargs["max_retries"] == 10


@pytest.mark.parametrize("task,body", TASKS, ids=["application", "talent_pool"])
@pytest.mark.parametrize("retries,final", [(0, False), (9, False), (10, True)])
def test_the_last_try_is_told_it_is_the_last(monkeypatch, task, body, retries, final):
    seen = {}

    async def record(*args, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(ai_tasks, body, record)

    task.push_request(retries=retries)
    try:
        task.run("00000000-0000-0000-0000-000000000001")
    finally:
        task.pop_request()

    assert seen["final_attempt"] is final


# --- the pipeline queues scoring itself when it finishes -------------------------------

LLM = LLMExtractionResult(skills=[], field_confidence={})


async def _application_using(db_session, submission, **row):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id)
    db_session.add(job)
    user = make_candidate_user()
    db_session.add(user)
    await db_session.flush()
    candidate = await make_candidate_profile(db_session, user)
    cv = CandidateCvs(
        candidate_id=candidate.id,
        key="cv.pdf",
        filename="cv.pdf",
        submission_id=submission.id,
    )
    db_session.add(cv)
    await db_session.flush()
    return await make_application(db_session, user.id, job.id, cv_id=cv.id, **row)


@pytest.mark.asyncio
async def test_finishing_a_parse_queues_scoring_for_the_waiting_application(
    db_session, monkeypatch
):
    queued = MagicMock()
    monkeypatch.setattr(ai_tasks.score_application_task, "delay", queued)
    waiting = {}

    async def set_up(submission):
        waiting["unscored"] = await _application_using(db_session, submission)
        waiting["scored"] = await _application_using(
            db_session, submission, ai_score=64
        )
        # Another CV entirely: nothing to do with this parse.
        other = ParsedCVSubmission(filename="other.pdf", parse_status=PENDING)
        db_session.add(other)
        await db_session.flush()
        waiting["elsewhere"] = await _application_using(db_session, other)

    await _run_pipeline_with_llm_result(
        monkeypatch, db_session, LLM, before_run=set_up
    )

    # Only the application that used this CV and has no score yet.
    queued.assert_called_once_with(str(waiting["unscored"].id))


@pytest.mark.asyncio
async def test_a_failure_to_queue_does_not_undo_the_parse(db_session, monkeypatch):
    monkeypatch.setattr(
        ai_tasks.score_application_task,
        "delay",
        MagicMock(side_effect=RuntimeError("broker down")),
    )

    async def set_up(submission):
        await _application_using(db_session, submission)

    submission = await _run_pipeline_with_llm_result(
        monkeypatch, db_session, LLM, before_run=set_up
    )

    assert submission.parse_status == COMPLETED
    assert submission.parsed_data is not None
