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
        "about_the_role": "Build scalable APIs for our platform.",
        "key_responsibilities": "Design, build and maintain backend services.",
        "requirements": "Strong Python skills and experience with FastAPI.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME,
        "work_model": WorkModel.HYBRID,
        "work_location": "LOCAL",
    }
    defaults.update(overrides)
    return JobCreateRequest(**defaults)


@pytest.mark.asyncio
async def test_create_job_returns_draft(db_session):
    """create_job always creates a DRAFT job."""
    from app.modules.users.models import EmployerProfile
    from tests.conftest import make_employer

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    # Gate requires a complete profile
    profile = EmployerProfile(
        user_id=employer.id,
        company_name="Test Corp",
        industry="Technology",
        company_size="11-50",
        is_profile_complete=True,
        kyc_status="APPROVED",
    )
    db_session.add(profile)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.create_job(make_create_request(), employer=employer)

    assert result.status == JobStatus.DRAFT.value
    assert result.employer_id == employer.id


@pytest.mark.asyncio
async def test_create_job_by_admin_is_immediately_active(db_session):
    """Admin-posted jobs skip the moderation queue and go straight to ACTIVE.

    Placeholder until admin roles are tiered — every admin is currently
    treated as an implicit reviewer of their own posts.
    """
    from tests.conftest import make_admin

    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.create_job(make_create_request(), employer=admin)

    assert result.status == JobStatus.ACTIVE.value
    assert result.moderation_status == "APPROVED"
    assert result.employer_id == admin.id


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
async def test_delete_job_removes_draft(db_session):
    """delete_job removes a DRAFT job owned by the caller."""
    from sqlalchemy import select

    from app.modules.jobs.models import Job
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.DRAFT.value, moderation_status="PENDING")
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    service = JobService(db_session)
    await service.delete_job(job_id, current_user=employer)

    result = await db_session.execute(select(Job).where(Job.id == job_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_job_raises_for_non_draft(db_session):
    """delete_job refuses to delete a job that has ever been published."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.ACTIVE.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(ValidationException):
        await service.delete_job(job.id, current_user=employer)


@pytest.mark.asyncio
async def test_delete_job_raises_for_wrong_owner(db_session):
    """delete_job raises PermissionDeniedException for a non-owner, non-admin caller."""
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
        await service.delete_job(job.id, current_user=other)


@pytest.mark.asyncio
async def test_delete_job_allowed_for_admin_on_others_draft(db_session):
    """delete_job allows an admin to delete any employer's draft job."""
    from sqlalchemy import select

    from app.modules.jobs.models import Job
    from tests.conftest import make_admin, make_employer, make_job

    employer = make_employer()
    admin = make_admin()
    db_session.add_all([employer, admin])
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.DRAFT.value)
    db_session.add(job)
    await db_session.flush()
    job_id = job.id

    service = JobService(db_session)
    await service.delete_job(job_id, current_user=admin)

    result = await db_session.execute(select(Job).where(Job.id == job_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_get_job_by_id_hides_draft_from_stranger(db_session):
    """get_job_by_id raises JobNotFoundError for a DRAFT job when the requester isn't the owner or an admin."""
    from tests.conftest import make_employer, make_job

    owner = make_employer()
    stranger = make_employer()
    db_session.add_all([owner, stranger])
    await db_session.flush()

    job = make_job(owner.id, status=JobStatus.DRAFT.value)
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)

    with pytest.raises(JobNotFoundError):
        await service.get_job_by_id(job.id, requesting_user=None)

    with pytest.raises(JobNotFoundError):
        await service.get_job_by_id(job.id, requesting_user=stranger)

    result = await service.get_job_by_id(job.id, requesting_user=owner)
    assert result.id == job.id


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
async def test_update_job_pulls_live_approved_job_offline_for_review(db_session):
    """Editing a live, approved job by its employer pulls it offline for re-review."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status="ACTIVE", moderation_status="APPROVED")
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.update_job(
        job.id, JobUpdateRequest(title="New Title"), current_user=employer
    )

    assert result.status == "DRAFT"
    assert result.moderation_status == "PENDING"


@pytest.mark.asyncio
async def test_update_job_by_admin_does_not_pull_offline(db_session):
    """Admin edits to a live, approved job don't trigger re-review — admin is the reviewer."""
    from tests.conftest import make_admin, make_employer, make_job

    employer = make_employer()
    admin = make_admin()
    db_session.add_all([employer, admin])
    await db_session.flush()

    job = make_job(employer.id, status="ACTIVE", moderation_status="APPROVED")
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.update_job(
        job.id, JobUpdateRequest(title="New Title"), current_user=admin
    )

    assert result.status == "ACTIVE"
    assert result.moderation_status == "APPROVED"


@pytest.mark.asyncio
async def test_update_job_does_not_clear_rejected_status(db_session):
    """Editing a REJECTED job no longer silently resubmits it — REJECTED is terminal until resubmit_job is called."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(
        employer.id,
        status=JobStatus.DRAFT.value,
        moderation_status="REJECTED",
        moderation_reason="Salary range looks fake",
    )
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.update_job(
        job.id, JobUpdateRequest(title="Fixed Title"), current_user=employer
    )

    assert result.title == "Fixed Title"
    assert result.moderation_status == "REJECTED"
    assert result.moderation_reason == "Salary range looks fake"


@pytest.mark.asyncio
async def test_resubmit_job_moves_rejected_to_pending(db_session):
    """resubmit_job is the only path from REJECTED back to PENDING, and clears the reason."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(
        employer.id,
        status=JobStatus.DRAFT.value,
        moderation_status="REJECTED",
        moderation_reason="Salary range looks fake",
    )
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    result = await service.resubmit_job(job.id, current_user=employer)

    assert result.moderation_status == "PENDING"
    assert result.moderation_reason is None


@pytest.mark.asyncio
async def test_resubmit_job_raises_when_not_rejected(db_session):
    """resubmit_job refuses to act on a job that isn't currently REJECTED."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id, status=JobStatus.DRAFT.value, moderation_status="PENDING")
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(ValidationException):
        await service.resubmit_job(job.id, current_user=employer)


@pytest.mark.asyncio
async def test_resubmit_job_raises_for_wrong_owner(db_session):
    """resubmit_job raises PermissionDeniedException for a non-owner, non-admin caller."""
    from tests.conftest import make_employer, make_job

    owner = make_employer()
    other = make_employer()
    db_session.add_all([owner, other])
    await db_session.flush()

    job = make_job(
        owner.id, status=JobStatus.DRAFT.value, moderation_status="REJECTED"
    )
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(PermissionDeniedException):
        await service.resubmit_job(job.id, current_user=other)


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
        await service.update_job(
            job.id, JobUpdateRequest(title="Stolen"), current_user=other
        )


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
    result = await service.get_job_by_id(job.id, requesting_user=None)

    assert result.id == job.id


@pytest.mark.asyncio
async def test_get_job_by_id_raises_for_unknown(db_session):
    """get_job_by_id raises JobNotFoundError for unknown ID."""
    service = JobService(db_session)

    with pytest.raises(JobNotFoundError):
        await service.get_job_by_id(uuid4(), requesting_user=None)


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
