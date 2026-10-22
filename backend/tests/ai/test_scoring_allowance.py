"""A company whose monthly AI-scoring allowance is spent has its next candidates saved and
shown as "not scored, plan limit reached", with no model call and no Sentry warning.

Both scoring tasks run for real, with the AI faked, exactly as in test_scoring_failure.py
(whose building blocks are reused here).
"""

import pytest

from app.core.config import settings
from app.modules.ai import tasks as ai_tasks
from app.modules.ai.models import FitScoringCost
from app.modules.ai.scoring_outcome import PLAN_LIMIT
from app.modules.billing.models import Plan
from app.modules.jobs.models import Job
from app.modules.users.models import User
from tests.ai.test_scoring_failure import (  # noqa: F401  (task_environment is a fixture)
    CASES,
    GOOD,
    READABLE,
    FakeAI,
    assert_unscored,
    task_environment,
    use_ai,
)
from tests.conftest import make_organization_for, make_subscription_for
from tests.interviews.conftest import make_talent_pool_profile


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _put_company_on(db_session, row, plan=None):
    """Give the employer who owns the candidate's job a company, on ``plan`` (None = Starter).
    Returns the job."""
    job_id = getattr(row, "job_id", None) or row.sourced_for_job_id
    job = await db_session.get(Job, job_id)
    employer = await db_session.get(User, job.employer_id)
    organization = await make_organization_for(db_session, employer)
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    return job, employer


async def _set_professional_allowance(db_session, scores):
    from sqlalchemy import select

    plan = (await db_session.execute(select(Plan).where(Plan.code == "professional"))).scalar_one()
    plan.monthly_ai_scores = scores
    await db_session.flush()


async def _already_scored(db_session, job, employer, how_many):
    """``how_many`` other candidates scored on this job this month (cost rows)."""
    for _ in range(how_many):
        other = await make_talent_pool_profile(db_session, employer.id)
        db_session.add(
            FitScoringCost(
                job_id=job.id,
                talent_pool_profile_id=other.id,
                input_tokens=100,
                output_tokens=50,
                model="test-model",
            )
        )
    await db_session.flush()


# --- over the allowance --------------------------------------------------------------------


@CASES
@pytest.mark.asyncio
async def test_a_starter_company_gets_no_scoring_and_the_row_says_the_plan_limit(
    db_session, monkeypatch, build
):
    row, run, _ = await build(db_session, READABLE)
    await _put_company_on(db_session, row)  # Starter: no AI scores outside the taste
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 0  # no model call, so no cost
    await db_session.refresh(row)
    assert_unscored(row, PLAN_LIMIT)


@CASES
@pytest.mark.asyncio
async def test_a_spent_allowance_is_not_reported_to_sentry(db_session, monkeypatch, build):
    row, run, _ = await build(db_session, READABLE)
    await _put_company_on(db_session, row)
    use_ai(monkeypatch, FakeAI(GOOD))
    reported = []
    monkeypatch.setattr(ai_tasks, "report_quality_signal", lambda *a, **k: reported.append(a))

    await run()

    assert reported == []  # expected, not a problem worth a warning


@CASES
@pytest.mark.asyncio
async def test_a_professional_company_with_no_room_left_is_refused_for_new_candidates(
    db_session, monkeypatch, build
):
    row, run, _ = await build(db_session, READABLE)
    job, employer = await _put_company_on(db_session, row, plan="professional")
    await _set_professional_allowance(db_session, 2)
    await _already_scored(db_session, job, employer, 2)  # both used
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 0
    await db_session.refresh(row)
    assert_unscored(row, PLAN_LIMIT)


# --- still scored --------------------------------------------------------------------------


@CASES
@pytest.mark.asyncio
async def test_a_professional_company_with_room_left_is_scored_normally(
    db_session, monkeypatch, build
):
    row, run, _ = await build(db_session, READABLE)
    job, employer = await _put_company_on(db_session, row, plan="professional")
    await _set_professional_allowance(db_session, 2)
    await _already_scored(db_session, job, employer, 1)  # one left
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 1
    await db_session.refresh(row)
    assert row.ai_score == 72
    assert row.ai_score_failure is None


@CASES
@pytest.mark.asyncio
async def test_a_candidate_already_scored_this_month_can_be_scored_again_at_the_limit(
    db_session, monkeypatch, build
):
    """A rescore (or a retry) adds no new score, so a spent allowance must not block it."""
    row, run, ids = await build(db_session, READABLE)
    job, employer = await _put_company_on(db_session, row, plan="professional")
    await _set_professional_allowance(db_session, 1)
    # This very candidate is the one score of the month.
    db_session.add(
        FitScoringCost(job_id=job.id, input_tokens=100, output_tokens=50, model="m", **ids)
    )
    await db_session.flush()
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 1
    await db_session.refresh(row)
    assert row.ai_score == 72


@CASES
@pytest.mark.asyncio
async def test_nothing_is_limited_while_plan_gating_is_off(db_session, monkeypatch, build):
    """Production today: gating is off. A Starter company is scored as before."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    row, run, _ = await build(db_session, READABLE)
    await _put_company_on(db_session, row)
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 1
    await db_session.refresh(row)
    assert row.ai_score == 72


@CASES
@pytest.mark.asyncio
async def test_a_company_with_no_record_and_the_existing_cases_are_unaffected(
    db_session, monkeypatch, build
):
    """The builders in test_scoring_failure give the job's owner no company, which must
    keep behaving as it always has: scored."""
    row, run, _ = await build(db_session, READABLE)
    ai = use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    assert ai.calls == 1


@CASES
@pytest.mark.asyncio
async def test_a_real_score_is_never_replaced_by_a_plan_limit_marker(db_session, monkeypatch, build):
    row, run, _ = await build(
        db_session,
        READABLE,
        ai_score=81,
        ai_fit_summary="Scored earlier.",
    )
    await _put_company_on(db_session, row)  # Starter, so the allowance is spent
    use_ai(monkeypatch, FakeAI(GOOD))

    await run()

    await db_session.refresh(row)
    assert row.ai_score == 81
    assert row.ai_score_failure is None
