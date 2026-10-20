"""Scoring a newly published job against the talent pool waits for the job's embedding.

When an admin creates a job, the task that makes its embedding and this one are queued at
the same moment, so this one often starts first. It used to crash with
`len(None)` (a Sentry error each time) and lean on Celery's default retries. Now it waits
on purpose and quietly, and a deleted job is not an error."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from celery.exceptions import Retry

from app.modules.ai import tasks as ai_tasks
from tests.conftest import make_employer, make_job


@pytest.fixture(autouse=True)
def task_environment(monkeypatch, db_session):
    """Run the task body on the test's own session."""

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


@pytest.fixture
def top_matches(monkeypatch):
    """The matching query is not what is under test: hand back two profiles."""
    profiles = [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())]
    monkeypatch.setattr(
        "app.modules.talent_pool.service.get_top_matches_for_job",
        AsyncMock(return_value=[(p, 0.8, []) for p in profiles]),
    )
    queued = MagicMock()
    monkeypatch.setattr(ai_tasks.score_talent_pool_profile_task, "delay", queued)
    return SimpleNamespace(profiles=profiles, queued=queued)


async def make_job_with(db_session, embedding):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id)
    job.job_embedding = embedding
    db_session.add(job)
    await db_session.flush()
    return job


@pytest.mark.asyncio
async def test_a_job_with_no_embedding_yet_is_waited_for_not_crashed_on(db_session, top_matches):
    job = await make_job_with(db_session, None)

    with pytest.raises(ai_tasks._EmbeddingNotReady):
        await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    top_matches.queued.assert_not_called()


@pytest.mark.asyncio
async def test_waiting_is_not_logged_as_an_error(db_session, top_matches, caplog):
    """An error log is what reached Sentry on every wait."""
    job = await make_job_with(db_session, None)

    with pytest.raises(ai_tasks._EmbeddingNotReady):
        await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    assert not [r for r in caplog.records if r.levelname in ("ERROR", "CRITICAL")]


@pytest.mark.asyncio
async def test_it_gives_up_quietly_after_the_last_try(db_session, top_matches, caplog):
    job = await make_job_with(db_session, None)

    await ai_tasks._score_job_against_talent_pool_async(str(job.id), final_attempt=True)

    top_matches.queued.assert_not_called()
    # One clear line saying it gave up, rather than silence.
    assert any("still has no embedding after" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_once_the_embedding_exists_the_top_profiles_are_queued(db_session, top_matches):
    job = await make_job_with(db_session, [0.1] * 1536)

    await ai_tasks._score_job_against_talent_pool_async(str(job.id))

    queued_ids = [call.args[0] for call in top_matches.queued.call_args_list]
    assert queued_ids == [str(p.id) for p in top_matches.profiles]
    assert all(call.args[1] == str(job.id) for call in top_matches.queued.call_args_list)


@pytest.mark.asyncio
async def test_a_job_deleted_since_it_was_queued_is_not_an_error(db_session, top_matches):
    await ai_tasks._score_job_against_talent_pool_async(str(uuid.uuid4()))  # must not raise

    top_matches.queued.assert_not_called()


def test_the_task_polls_every_30_seconds_for_up_to_6_tries(monkeypatch):
    async def waiting(*args, **kwargs):
        raise ai_tasks._EmbeddingNotReady("no embedding yet")

    retry = MagicMock(side_effect=Retry())
    monkeypatch.setattr(ai_tasks, "_score_job_against_talent_pool_async", waiting)
    monkeypatch.setattr(ai_tasks.score_job_against_talent_pool_task, "retry", retry)

    with pytest.raises(Retry):
        ai_tasks.score_job_against_talent_pool_task.run(str(uuid.uuid4()))

    assert retry.call_args.kwargs["countdown"] == 30
    assert retry.call_args.kwargs["max_retries"] == 6


@pytest.mark.parametrize("retries,final", [(0, False), (5, False), (6, True)])
def test_the_last_try_is_told_it_is_the_last(monkeypatch, retries, final):
    seen = {}

    async def record(*args, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(ai_tasks, "_score_job_against_talent_pool_async", record)
    task = ai_tasks.score_job_against_talent_pool_task

    task.push_request(retries=retries)
    try:
        task.run(str(uuid.uuid4()))
    finally:
        task.pop_request()

    assert seen["final_attempt"] is final
