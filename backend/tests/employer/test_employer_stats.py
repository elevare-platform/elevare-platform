"""Tests for GET /employer/stats endpoint."""

import pytest

from app.modules.jobs.enums import JobStatus
from tests.conftest import make_job
from tests.jobs.test_jobs_router import register_and_promote


@pytest.mark.asyncio
async def test_employer_stats_correct_counts(client, db_session):
    """Stats endpoint returns correct counts scoped to the authenticated employer."""
    from sqlalchemy import select

    from app.modules.users.models import User

    token = await register_and_promote(client, db_session, "EMPLOYER")

    # Resolve the employer's user_id from DB
    result = await db_session.execute(select(User).order_by(User.created_at.desc()))
    employer = result.scalars().first()

    # Seed: 1 active, 2 draft, 1 closed
    jobs = [
        make_job(employer.id, status=JobStatus.ACTIVE.value, title="Active Job"),
        make_job(employer.id, status=JobStatus.DRAFT.value, title="Draft Job 1"),
        make_job(employer.id, status=JobStatus.DRAFT.value, title="Draft Job 2"),
        make_job(employer.id, status=JobStatus.CLOSED.value, title="Closed Job"),
    ]
    db_session.add_all(jobs)
    await db_session.flush()

    response = await client.get(
        "/api/v1/employer/stats",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_jobs"] == 4
    assert data["active_jobs"] == 1
    assert data["draft_jobs"] == 2
    assert data["closed_jobs"] == 1
    assert data["total_applications"] == 0  # Application model not yet in Phase 4
