"""Publishing a job no longer queues AI scorings the company has no allowance for.

Publishing used to queue up to 20 scorings of the talent pool on every plan, so a Starter
company could cost 20 model calls each time it published (plan 15.2, gap G2). Now it queues
none when the company has no room, and never more than the room it has.
"""

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.ai import tasks as ai_tasks
from app.modules.billing.models import Plan
from app.modules.users.models import User
from tests.ai import test_job_scoring_waits_for_embedding as base
from tests.conftest import make_organization_for, make_subscription_for

# The task environment and the patched matching query are shared with the test file that
# first needed them; assigning them here makes pytest offer them to these tests too.
task_environment = base.task_environment
top_matches = base.top_matches
make_job_with = base.make_job_with


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _published_job(db_session, plan=None):
    job = await make_job_with(db_session, [0.1] * 1536)
    employer = await db_session.get(User, job.employer_id)
    organization = await make_organization_for(db_session, employer)
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    return job


def _limit_asked_for(top_matches_fixture):
    """The `limit` the task asked the matching query for, from the patched query's calls."""
    from app.modules.talent_pool import service as pool_service

    return pool_service.get_top_matches_for_job.call_args.kwargs["limit"]


@pytest.mark.asyncio
async def test_a_starter_company_publishing_queues_no_scoring_at_all(db_session, top_matches):
    job = await _published_job(db_session)

    await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    top_matches.queued.assert_not_called()


@pytest.mark.asyncio
async def test_a_professional_company_with_plenty_of_room_gets_the_usual_twenty(
    db_session, top_matches
):
    job = await _published_job(db_session, plan="professional")

    await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    assert _limit_asked_for(top_matches) == 20
    assert top_matches.queued.call_count == 2  # the two profiles the patched query returns


@pytest.mark.asyncio
async def test_never_more_than_the_room_the_company_has_left(db_session, top_matches):
    job = await _published_job(db_session, plan="professional")
    plan = (await db_session.execute(select(Plan).where(Plan.code == "professional"))).scalar_one()
    plan.monthly_ai_scores = 3
    await db_session.flush()

    await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    assert _limit_asked_for(top_matches) == 3


@pytest.mark.asyncio
async def test_a_company_with_no_record_is_unaffected(db_session, top_matches):
    job = await make_job_with(db_session, [0.1] * 1536)  # an owner with no company

    await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    assert _limit_asked_for(top_matches) == 20


@pytest.mark.asyncio
async def test_nothing_changes_while_plan_gating_is_off(db_session, top_matches, monkeypatch):
    """Production today: gating is off, so a Starter company still gets the usual twenty."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    job = await _published_job(db_session)

    await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    assert _limit_asked_for(top_matches) == 20
