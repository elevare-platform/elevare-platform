"""The count behind the badge on the admin Jobs menu: jobs that are waiting for review.

The shared dev database already holds other jobs, so each test reads the count first and checks
how much it moves."""

import pytest

from app.modules.auth.jwt_handler import create_token_pair
from app.modules.jobs.enums import JobStatus
from tests.conftest import make_admin, make_employer, make_job

URL = "/api/v1/admin/jobs/pending-count"


async def _headers(db_session, user):
    db_session.add(user)
    await db_session.flush()
    token = create_token_pair(user.id, user.role)["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _count(client, headers) -> int:
    response = await client.get(URL, headers=headers)
    assert response.status_code == 200
    return response.json()["count"]


async def _employer_with_jobs(db_session, *jobs):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    for overrides in jobs:
        db_session.add(make_job(employer.id, **overrides))
    await db_session.flush()


@pytest.mark.asyncio
async def test_only_drafts_waiting_for_review_are_counted(client, db_session):
    headers = await _headers(db_session, make_admin())
    before = await _count(client, headers)

    await _employer_with_jobs(
        db_session,
        {"status": JobStatus.DRAFT.value, "moderation_status": "PENDING"},  # counted
        {"status": JobStatus.DRAFT.value, "moderation_status": "PENDING"},  # counted
        {"status": JobStatus.DRAFT.value, "moderation_status": "APPROVED"},  # already reviewed
        {"status": JobStatus.DRAFT.value, "moderation_status": "REJECTED"},  # already reviewed
        {"status": JobStatus.ACTIVE.value, "moderation_status": "APPROVED"},  # live
        {"status": JobStatus.CLOSED.value, "moderation_status": "APPROVED"},  # over
    )

    assert await _count(client, headers) == before + 2


@pytest.mark.asyncio
async def test_the_hidden_general_interest_job_is_not_counted(client, db_session):
    headers = await _headers(db_session, make_admin())
    before = await _count(client, headers)

    await _employer_with_jobs(
        db_session,
        {"status": JobStatus.DRAFT.value, "moderation_status": "PENDING", "is_general_interest": True},
    )

    assert await _count(client, headers) == before


@pytest.mark.asyncio
async def test_an_employer_cannot_read_it(client, db_session):
    headers = await _headers(db_session, make_employer())

    assert (await client.get(URL, headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_it_needs_a_login(client):
    assert (await client.get(URL)).status_code == 401
