"""Tests for JobService — business logic layer."""

from uuid import uuid4

import pytest

from app.core.exceptions import (
    JobNotFoundError,
    PermissionDeniedException,
    ValidationException,
)
from app.modules.jobs.enums import ContractType, JobStatus, WorkModel
from app.modules.jobs.schemas import JobCreateRequest, JobFilterParams, JobUpdateRequest
from app.modules.jobs.service import JobService


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
async def test_create_job_returns_draft(db_session):
    """create_job always creates a DRAFT job."""
    from tests.conftest import make_employer

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.create_job(make_create_request(), employer=employer)

    assert result.status == JobStatus.DRAFT.value
    assert result.employer_id == employer.id


@pytest.mark.asyncio
async def test_publish_job_transitions_to_active(db_session):
    """publish_job transitions DRAFT → ACTIVE."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.DRAFT.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.publish_job(job.id, current_user=employer)

    assert result.status == JobStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_publish_job_raises_for_wrong_owner(db_session):
    """publish_job raises PermissionDeniedException for non-owner."""
    from tests.conftest import make_employer, make_job

    owner = make_employer()
    other = make_employer()
    db_session.add_all([owner, other])
    await db_session.flush()

    job = make_job(owner.id, status=JobStatus.DRAFT.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(PermissionDeniedException):
        await service.publish_job(job.id, current_user=other)


@pytest.mark.asyncio
async def test_publish_active_job_raises_validation_error(db_session):
    """publish_job on an ACTIVE job raises ValidationException (invalid transition)."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.ACTIVE.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(ValidationException):
        await service.publish_job(job.id, current_user=employer)


@pytest.mark.asyncio
async def test_close_job_transitions_to_closed(db_session):
    """close_job transitions ACTIVE → CLOSED."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.ACTIVE.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.close_job(job.id, current_user=employer)

    assert result.status == JobStatus.CLOSED.value


@pytest.mark.asyncio
async def test_close_draft_job_raises_validation_error(db_session):
    """close_job on a DRAFT job raises ValidationException (invalid transition)."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.DRAFT.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(ValidationException):
        await service.close_job(job.id, current_user=employer)


@pytest.mark.asyncio
async def test_update_job_applies_changes(db_session):
    """update_job applies partial changes to the job."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, title="Old Title")
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.update_job(
        job.id,
        JobUpdateRequest(title="New Title"),
        current_user=employer,
    )

    assert result.title == "New Title"


@pytest.mark.asyncio
async def test_update_job_raises_for_wrong_owner(db_session):
    """update_job raises PermissionDeniedException for non-owner."""
    from tests.conftest import make_employer, make_job

    owner = make_employer()
    other = make_employer()
    db_session.add_all([owner, other])
    await db_session.flush()

    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(PermissionDeniedException):
        await service.update_job(job.id, JobUpdateRequest(title="Stolen"), current_user=other)


@pytest.mark.asyncio
async def test_get_job_by_id_returns_job(db_session):
    """get_job_by_id returns the correct job."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.get_job_by_id(job.id)

    assert result.id == job.id


@pytest.mark.asyncio
async def test_get_job_by_id_raises_for_unknown(db_session):
    """get_job_by_id raises JobNotFoundError for unknown ID."""
    service = JobService(db_session)

    with pytest.raises(JobNotFoundError):
        await service.get_job_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_jobs_returns_only_active(db_session):
    """list_jobs returns only ACTIVE jobs."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    active = make_job(employer.id, status=JobStatus.ACTIVE.value, title="Active")
    draft = make_job(employer.id, status=JobStatus.DRAFT.value, title="Draft")
    db_session.add_all([active, draft])
    await db_session.flush()

    service = JobService(db_session)
    result = await service.list_jobs(JobFilterParams())

    titles = [j.title for j in result.items]
    assert "Active" in titles
    assert "Draft" not in titles


@pytest.mark.asyncio
async def test_list_employer_jobs_returns_own_only(db_session):
    """list_employer_jobs returns only the employer's own jobs."""
    from tests.conftest import make_employer, make_job

    employer1 = make_employer()
    employer2 = make_employer()
    db_session.add_all([employer1, employer2])
    await db_session.flush()

    job1 = make_job(employer1.id, title="Mine")
    job2 = make_job(employer2.id, title="Not Mine")
    db_session.add_all([job1, job2])
    await db_session.flush()

    service = JobService(db_session)
    result = await service.list_employer_jobs(employer=employer1)

    titles = [j.title for j in result.items]
    assert "Mine" in titles
    assert "Not Mine" not in titles
