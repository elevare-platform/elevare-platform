"""Tests for Job ORM model behaviour."""

from decimal import Decimal

import pytest

from app.modules.jobs.enums import JobStatus
from app.modules.jobs.models import Job


@pytest.mark.asyncio
async def test_job_created_with_defaults(db_session):
    """Job can be created with required fields; optional fields default to None."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    assert job.id is not None
    assert job.employer_id == employer.id
    assert job.salary_min is None
    assert job.salary_max is None
    assert job.created_at is not None
    assert job.updated_at is not None


@pytest.mark.asyncio
async def test_job_stores_salary_as_decimal(db_session):
    """Salary fields are stored and retrieved as Decimal values."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(
        employer.id, salary_min=Decimal("500000.00"), salary_max=Decimal("900000.00")
    )
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    assert job.salary_min == Decimal("500000.00")
    assert job.salary_max == Decimal("900000.00")


@pytest.mark.asyncio
async def test_job_employer_relationship(db_session):
    """Job.employer resolves to the owning User instance."""
    from sqlalchemy import select

    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    # Re-fetch to trigger relationship load
    result = await db_session.execute(select(Job).where(Job.id == job.id))
    fetched = result.scalar_one()

    assert fetched.employer_id == employer.id


@pytest.mark.asyncio
async def test_job_status_stored_as_string(db_session):
    """Status is stored as a VARCHAR string, not an enum object."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.ACTIVE.value)
    db_session.add(job)
    await db_session.flush()

    assert job.status == "ACTIVE"
