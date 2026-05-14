"""Tests for JobRepository — direct DB operations."""

from uuid import uuid4

import pytest

from app.core.exceptions import JobNotFoundError
from app.modules.jobs.enums import ContractType, JobStatus, WorkModel
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import JobCreateRequest, JobFilterParams, JobUpdateRequest


def make_create_request(**overrides) -> JobCreateRequest:
    """Build a JobCreateRequest with sensible defaults."""
    defaults = {
        "title": "Backend Engineer",
        "description": "Build scalable APIs for our platform.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME,
        "work_model": WorkModel.HYBRID,
    }
    defaults.update(overrides)
    return JobCreateRequest(**defaults)


@pytest.mark.asyncio
async def test_create_job_sets_draft_status(db_session):
    """create() always sets status to DRAFT regardless of input."""
    from tests.conftest import make_employer

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    repo = JobRepository(db_session)
    job = await repo.create(make_create_request(), employer_id=employer.id)

    assert job.status == JobStatus.DRAFT.value
    assert job.employer_id == employer.id
    assert job.id is not None


@pytest.mark.asyncio
async def test_create_job_sets_employer_id(db_session):
    """create() sets employer_id from the parameter, not from the schema."""
    from tests.conftest import make_employer

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    repo = JobRepository(db_session)
    job = await repo.create(make_create_request(), employer_id=employer.id)

    assert job.employer_id == employer.id


@pytest.mark.asyncio
async def test_get_by_id_returns_job(db_session):
    """get_by_id returns the correct job."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    repo = JobRepository(db_session)
    fetched = await repo.get_by_id(job.id)

    assert fetched.id == job.id
    assert fetched.title == job.title


@pytest.mark.asyncio
async def test_get_by_id_raises_for_unknown(db_session):
    """get_by_id raises JobNotFoundError for a non-existent ID."""
    repo = JobRepository(db_session)

    with pytest.raises(JobNotFoundError):
        await repo.get_by_id(uuid4())


@pytest.mark.asyncio
async def test_update_applies_partial_changes(db_session):
    """update() only changes fields present in the request."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, title="Original Title")
    db_session.add(job)
    await db_session.flush()

    repo = JobRepository(db_session)
    updated = await repo.update(job, JobUpdateRequest(title="New Title"))

    assert updated.title == "New Title"
    assert updated.location == job.location  # unchanged


@pytest.mark.asyncio
async def test_set_status_changes_status(db_session):
    """set_status() updates the job status correctly."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.DRAFT.value)
    db_session.add(job)
    await db_session.flush()

    repo = JobRepository(db_session)
    updated = await repo.set_status(job, JobStatus.ACTIVE)

    assert updated.status == JobStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_list_active_returns_only_active(db_session):
    """list_active() returns only ACTIVE jobs."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    active = make_job(employer.id, status=JobStatus.ACTIVE.value, title="Active Job")
    draft = make_job(employer.id, status=JobStatus.DRAFT.value, title="Draft Job")
    db_session.add_all([active, draft])
    await db_session.flush()

    repo = JobRepository(db_session)
    result = await repo.list_active(JobFilterParams(), limit=20)

    titles = [j.title for j in result["items"]]
    assert "Active Job" in titles
    assert "Draft Job" not in titles


@pytest.mark.asyncio
async def test_list_active_filters_by_work_model(db_session):
    """list_active() filters by work_model when provided."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    remote = make_job(employer.id, work_model=WorkModel.REMOTE.value, title="Remote Job")
    onsite = make_job(employer.id, work_model=WorkModel.ONSITE.value, title="Onsite Job")
    db_session.add_all([remote, onsite])
    await db_session.flush()

    repo = JobRepository(db_session)
    result = await repo.list_active(JobFilterParams(work_model=WorkModel.REMOTE), limit=20)

    titles = [j.title for j in result["items"]]
    assert "Remote Job" in titles
    assert "Onsite Job" not in titles


@pytest.mark.asyncio
async def test_list_by_employer_returns_own_jobs_only(db_session):
    """list_by_employer() returns only jobs owned by the given employer."""
    from tests.conftest import make_employer, make_job

    employer1 = make_employer()
    employer2 = make_employer()
    db_session.add_all([employer1, employer2])
    await db_session.flush()

    job1 = make_job(employer1.id, title="Employer 1 Job")
    job2 = make_job(employer2.id, title="Employer 2 Job")
    db_session.add_all([job1, job2])
    await db_session.flush()

    repo = JobRepository(db_session)
    result = await repo.list_by_employer(employer1.id, limit=20)

    titles = [j.title for j in result["items"]]
    assert "Employer 1 Job" in titles
    assert "Employer 2 Job" not in titles


@pytest.mark.asyncio
async def test_list_all_returns_all_statuses(db_session):
    """list_all() returns jobs of every status."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    jobs = [
        make_job(employer.id, status=JobStatus.ACTIVE.value, title="Active"),
        make_job(employer.id, status=JobStatus.DRAFT.value, title="Draft"),
        make_job(employer.id, status=JobStatus.CLOSED.value, title="Closed"),
    ]
    db_session.add_all(jobs)
    await db_session.flush()

    repo = JobRepository(db_session)
    result = await repo.list_all(limit=20)

    titles = [j.title for j in result["items"]]
    assert "Active" in titles
    assert "Draft" in titles
    assert "Closed" in titles
