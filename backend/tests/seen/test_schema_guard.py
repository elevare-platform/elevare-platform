"""New code meeting an old schema: for the seconds of a deploy before ``alembic upgrade head`` has
run, a page that only gains an extra (the "new" markers, a scoring profile, a score report) must
still load. The test session is one rolled-back transaction, so dropping a table here is undone."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.core.schema_guard import tolerate_missing
from app.modules.interviews.scoring_profile_service import load_profile
from app.modules.seen.service import SeenService
from app.modules.talent_pool.service import TalentPoolService
from tests.conftest import make_employer, make_organization_for, make_subscription_for
from tests.seen.test_seen import cv


async def employer_with_plan(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    await make_subscription_for(db_session, organization)
    return employer


@pytest.mark.asyncio
async def test_a_missing_table_gives_the_fallback_and_the_session_stays_usable(db_session):
    await db_session.execute(text("DROP TABLE job_scoring_profiles"))

    result = await load_profile(db_session, uuid.uuid4())

    assert result is None
    assert (await db_session.execute(text("SELECT 1"))).scalar_one() == 1


@pytest.mark.asyncio
async def test_any_other_database_error_is_still_raised(db_session):
    async def broken():
        await db_session.execute(text("SELECT no_such_function_anywhere()"))

    with pytest.raises(ProgrammingError):
        await tolerate_missing(db_session, broken, None)


@pytest.mark.asyncio
async def test_the_talent_pool_still_lists_when_the_seen_tables_are_not_there_yet(db_session):
    employer = await employer_with_plan(db_session)
    profile = await cv(db_session, employer.id, datetime.now(UTC) - timedelta(days=1))
    await db_session.execute(text("DROP TABLE talent_pool_profile_views, employer_seen_baselines CASCADE"))

    service = TalentPoolService(db_session, cv_service=None)
    result = await service.list_profiles(
        status=None, source=None, job_id=None, cursor=None, limit=50, current_user=employer
    )

    assert [(item.id, item.is_new) for item in result["items"]] == [(profile.id, False)]
    assert await service.new_count(employer) == 0


@pytest.mark.asyncio
async def test_marking_a_cv_opened_does_nothing_rather_than_failing_without_the_tables(db_session):
    employer = await employer_with_plan(db_session)
    profile = await cv(db_session, employer.id, datetime.now(UTC))
    await db_session.execute(text("DROP TABLE talent_pool_profile_views, employer_seen_baselines CASCADE"))

    await SeenService(db_session).mark_profile_opened(employer.id, profile.id)

    assert await SeenService(db_session).baseline(employer.id) is None
