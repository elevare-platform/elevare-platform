"""A candidate who could not be scored says so; they are never given a fake 0.

Both scoring tasks (talent pool profiles and applications) run for real against the
shared test session, with the AI service faked. The old behaviour these guard against:
a failed or cut-off call was saved as a score of 0 WITH the hashes of the CV and job,
so it looked like a real result and the hash cache froze it for good; and an unreadable
CV was sent to the model anyway and scored (as 0)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.modules.ai import tasks as ai_tasks
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import FitScoringCost, ParsedCVSubmission
from app.modules.ai.schema import FitReasoningResult
from app.modules.ai.scoring_outcome import CV_UNREADABLE, SCORING_FAILED, ScoringFailed
from app.modules.candidates.models import CandidateCvs
from tests.conftest import make_employer, make_job
from tests.interviews.conftest import (
    make_application,
    make_candidate_profile,
    make_candidate_user,
    make_talent_pool_profile,
)

NULL_JOB = {"company": None, "title": None, "description": None, "is_current": False}
READABLE = {
    "work_history": [
        {"title": "Sales Manager", "company": "Unilever", "description": "Led sales"}
    ],
    "education": [],
    "skills": ["Excel"],
    "current_title": "Sales Manager",
}
UNREADABLE = {"work_history": [NULL_JOB], "education": [], "skills": []}

GOOD = FitReasoningResult(
    score=72,
    strengths=["Sales leadership"],
    weaknesses=["No retail"],
    fit_summary="A strong fit for the role.",
    input_tokens=300,
    output_tokens=120,
    model="claude-haiku-4-5",
)
FAILED = FitReasoningResult(
    failed=True, input_tokens=300, output_tokens=2048, model="claude-haiku-4-5"
)
FAILED_BEFORE_ANY_REPLY = FitReasoningResult(failed=True, model="claude-haiku-4-5")


class FakeAI:
    """Stands in for AnthropicCVExtractionService: hands out the given results in
    order and records how many model calls were made."""

    def __init__(self, *results):
        self._results = list(results)
        self.calls = 0
        self._client = SimpleNamespace(close=AsyncMock())

    async def generate_fit_reasoning(self, candidate_context, job_context, model=None):
        self.calls += 1
        return self._results.pop(0)


@pytest.fixture(autouse=True)
def task_environment(monkeypatch, db_session):
    """Run the task bodies on the test's own session, without tiering (one model)."""
    monkeypatch.setattr(ai_tasks.settings, "ai_tiering_enabled", False)

    class _SameSession:
        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(
        ai_tasks,
        "create_async_engine",
        lambda *a, **k: SimpleNamespace(dispose=AsyncMock()),
    )
    monkeypatch.setattr(ai_tasks, "async_sessionmaker", lambda *a, **k: lambda: _SameSession())


def use_ai(monkeypatch, fake: FakeAI) -> FakeAI:
    monkeypatch.setattr(ai_tasks, "AnthropicCVExtractionService", lambda: fake)
    return fake


# --- the two kinds of candidate, built the same way for every test ----------------


async def _job(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    return employer, job


async def _submission(
    db_session, parsed_data, parse_status=CVParsingStatus.COMPLETED.value
):
    submission = ParsedCVSubmission(
        filename="cv.pdf", parse_status=parse_status, parsed_data=parsed_data
    )
    db_session.add(submission)
    await db_session.flush()
    return submission


async def talent_pool_case(
    db_session, parsed_data, parse_status=CVParsingStatus.COMPLETED.value, **row
):
    employer, job = await _job(db_session)
    submission = await _submission(db_session, parsed_data, parse_status)
    profile = await make_talent_pool_profile(
        db_session,
        employer.id,
        parsed_submission_id=submission.id,
        sourced_for_job_id=job.id,
        **row,
    )
    return profile, lambda: ai_tasks._score_talent_pool_profile_async(
        str(profile.id), str(job.id)
    ), {"talent_pool_profile_id": profile.id}


async def application_case(
    db_session, parsed_data, parse_status=CVParsingStatus.COMPLETED.value, **row
):
    _, job = await _job(db_session)
    user = make_candidate_user()
    db_session.add(user)
    await db_session.flush()
    candidate = await make_candidate_profile(db_session, user)
    submission = await _submission(db_session, parsed_data, parse_status)
    cv = CandidateCvs(
        candidate_id=candidate.id,
        key="cv.pdf",
        filename="cv.pdf",
        submission_id=submission.id,
    )
    db_session.add(cv)
    await db_session.flush()
    # An application belongs to the candidate's USER; the CV to their profile.
    application = await make_application(
        db_session, user.id, job.id, cv_id=cv.id, **row
    )
    return application, lambda: ai_tasks._score_application_async(
        str(application.id)
    ), {"application_id": application.id}


CASES = pytest.mark.parametrize(
    "build", [talent_pool_case, application_case], ids=["talent_pool", "application"]
)


async def cost_rows(db_session, **ids):
    column, value = next(iter(ids.items()))
    return (
        (
            await db_session.execute(
                select(FitScoringCost).where(getattr(FitScoringCost, column) == value)
            )
        )
        .scalars()
        .all()
    )


def assert_unscored(row, reason):
    assert row.ai_score is None
    assert row.ai_fit_summary is None
    assert row.ai_strengths is None
    assert row.ai_score_job_hash is None
    assert row.ai_score_cv_hash is None
    assert row.ai_score_failure == reason


# --- B1: an unreadable CV is never sent to the model --------------------------------


@CASES
@pytest.mark.asyncio
async def test_an_unreadable_cv_is_not_scored_and_says_why(
    db_session, monkeypatch, build
):
    row, run, _ = await build(db_session, UNREADABLE)
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 0  # no model call, so no cost
    await db_session.refresh(row)
    assert_unscored(row, CV_UNREADABLE)


@CASES
@pytest.mark.asyncio
async def test_a_cv_that_failed_to_parse_at_all_says_it_is_unreadable(
    db_session, monkeypatch, build
):
    row, run, _ = await build(
        db_session, None, parse_status=CVParsingStatus.FAILED.value
    )
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 0
    await db_session.refresh(row)
    assert_unscored(row, CV_UNREADABLE)


@CASES
@pytest.mark.asyncio
async def test_an_unreadable_cv_replaces_a_fake_zero_left_by_the_old_behaviour(
    db_session, monkeypatch, build
):
    """The old failure shape: 0, no summary, with hashes that froze it."""
    row, run, _ = await build(
        db_session,
        UNREADABLE,
        ai_score=0,
        ai_score_job_hash="old-job",
        ai_score_cv_hash="old-cv",
        ai_score_computed_at=datetime.now(UTC),
    )
    use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    await db_session.refresh(row)
    assert_unscored(row, CV_UNREADABLE)


@CASES
@pytest.mark.asyncio
async def test_an_unreadable_cv_never_overwrites_a_real_score(
    db_session, monkeypatch, build
):
    row, run, _ = await build(
        db_session,
        UNREADABLE,
        ai_score=64,
        ai_fit_summary="A solid fit.",
        ai_score_job_hash="job",
        ai_score_cv_hash="cv",
    )
    use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    await db_session.refresh(row)
    assert (row.ai_score, row.ai_fit_summary) == (64, "A solid fit.")
    assert row.ai_score_failure is None


# --- B2: a failed call is never saved as a score ------------------------------------


@CASES
@pytest.mark.asyncio
async def test_a_failed_call_leaves_no_score_no_hash_and_says_why(
    db_session, monkeypatch, build
):
    row, run, ids = await build(db_session, READABLE)
    ai = use_ai(monkeypatch, FakeAI(FAILED, FAILED))

    with pytest.raises(ScoringFailed):
        await run()

    assert ai.calls == 2  # tried, then once more
    await db_session.refresh(row)
    assert_unscored(row, SCORING_FAILED)
    assert row.ai_score_computed_at is None


@CASES
@pytest.mark.asyncio
async def test_a_failed_call_is_still_billed(db_session, monkeypatch, build):
    row, run, ids = await build(db_session, READABLE)
    use_ai(monkeypatch, FakeAI(FAILED, FAILED_BEFORE_ANY_REPLY))

    with pytest.raises(ScoringFailed):
        await run()

    rows = await cost_rows(db_session, **ids)
    # The cut-off reply cost tokens; the call that never got a reply cost none.
    assert [(r.input_tokens, r.output_tokens) for r in rows] == [(300, 2048)]


@CASES
@pytest.mark.asyncio
async def test_a_second_try_that_works_is_saved_and_clears_the_failure(
    db_session, monkeypatch, build
):
    row, run, _ = await build(db_session, READABLE)
    ai = use_ai(monkeypatch, FakeAI(FAILED, GOOD))

    await run()

    assert ai.calls == 2
    await db_session.refresh(row)
    assert (row.ai_score, row.ai_fit_summary) == (72, "A strong fit for the role.")
    assert row.ai_score_failure is None
    assert row.ai_score_job_hash and row.ai_score_cv_hash


@CASES
@pytest.mark.asyncio
async def test_a_failed_row_is_tried_again_not_skipped_as_already_scored(
    db_session, monkeypatch, build
):
    row, run, _ = await build(db_session, READABLE)
    use_ai(monkeypatch, FakeAI(FAILED, FAILED))
    with pytest.raises(ScoringFailed):
        await run()

    ai = use_ai(monkeypatch, FakeAI(GOOD))
    await run()  # the next trigger: not blocked by the cache

    assert ai.calls == 1
    await db_session.refresh(row)
    assert row.ai_score == 72
    assert row.ai_score_failure is None


@CASES
@pytest.mark.asyncio
async def test_a_failed_call_never_overwrites_a_real_score(
    db_session, monkeypatch, build
):
    row, run, _ = await build(
        db_session,
        READABLE,
        ai_score=64,
        ai_fit_summary="A solid fit.",
        ai_score_job_hash="old-job-hash",  # the job changed since, so it rescores
        ai_score_cv_hash="old-cv-hash",
    )
    use_ai(monkeypatch, FakeAI(FAILED, FAILED))

    with pytest.raises(ScoringFailed):
        await run()

    await db_session.refresh(row)
    assert (row.ai_score, row.ai_fit_summary) == (64, "A solid fit.")
    assert row.ai_score_failure is None


@CASES
@pytest.mark.asyncio
async def test_a_genuine_zero_with_a_summary_is_a_real_score_and_is_cached(
    db_session, monkeypatch, build
):
    """0 is a legitimate score for a poor fit. It is saved as one, and not retried."""
    poor_fit = FitReasoningResult(
        score=0,
        strengths=[],
        weaknesses=["Wrong field entirely"],
        fit_summary="Nothing in this CV relates to the role.",
        input_tokens=300,
        output_tokens=100,
        model="claude-haiku-4-5",
    )
    row, run, _ = await build(db_session, READABLE)
    use_ai(monkeypatch, FakeAI(poor_fit))
    await run()

    await db_session.refresh(row)
    assert row.ai_score == 0
    assert row.ai_fit_summary
    assert row.ai_score_failure is None

    second = use_ai(monkeypatch, FakeAI(GOOD))
    await run()
    assert second.calls == 0  # cache hit: scored already


# --- the escalation rule itself ---------------------------------------------------------


@pytest.mark.asyncio
async def test_with_tiering_on_a_failed_fast_call_escalates_to_the_deep_model(monkeypatch):
    monkeypatch.setattr(ai_tasks.settings, "ai_tiering_enabled", True)
    models = []

    class Recorder(FakeAI):
        async def generate_fit_reasoning(self, candidate_context, job_context, model=None):
            models.append(model)
            return await super().generate_fit_reasoning(candidate_context, job_context, model)

    reasoning, attempts = await ai_tasks._generate_tiered_fit_reasoning(
        Recorder(FAILED, GOOD), "cv", "job"
    )

    assert models == [ai_tasks.settings.anthropic_model_fast, ai_tasks.settings.anthropic_model]
    assert not reasoning.failed
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_with_tiering_off_a_failed_call_is_retried_once_on_the_same_model(monkeypatch):
    monkeypatch.setattr(ai_tasks.settings, "ai_tiering_enabled", False)
    models = []

    class Recorder(FakeAI):
        async def generate_fit_reasoning(self, candidate_context, job_context, model=None):
            models.append(model)
            return await super().generate_fit_reasoning(candidate_context, job_context, model)

    reasoning, attempts = await ai_tasks._generate_tiered_fit_reasoning(
        Recorder(FAILED, FAILED), "cv", "job"
    )

    assert models == [ai_tasks.settings.anthropic_model] * 2
    assert reasoning.failed
    assert len(attempts) == 2


@pytest.mark.asyncio
async def test_a_good_first_answer_makes_no_second_call_when_tiering_is_off(monkeypatch):
    monkeypatch.setattr(ai_tasks.settings, "ai_tiering_enabled", False)
    fake = FakeAI(GOOD)

    reasoning, attempts = await ai_tasks._generate_tiered_fit_reasoning(fake, "cv", "job")

    assert fake.calls == 1
    assert len(attempts) == 1
    assert reasoning.score == 72
