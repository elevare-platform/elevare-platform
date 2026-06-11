"""Tests for AdminService — business logic layer."""

from uuid import uuid4

import pytest

from app.core.exceptions import (
    CannotModifyAdminException,
    JobNotFoundError,
    UserNotFoundException,
    ValidationException,
)
from app.modules.admin.service import AdminService
from app.modules.jobs.enums import ModerationStatus
from app.modules.users.enums import AccountStatus, UserRole
from tests.conftest import make_employer, make_job, make_user


@pytest.mark.asyncio
async def test_list_users_with_role_filter(db_session):
    """list_users returns correct subset when filtering by role."""
    candidate = make_user(role=UserRole.CANDIDATE.value)
    employer = make_employer()
    db_session.add_all([candidate, employer])
    await db_session.flush()

    service = AdminService(db_session)
    # Filter by role AND by known email to isolate from pre-existing data
    result = await service.list_users(
        role=UserRole.CANDIDATE.value,
        search=candidate.email,
    )

    assert result["count"] == 1
    assert result["items"][0].role == UserRole.CANDIDATE.value


@pytest.mark.asyncio
async def test_list_users_with_search(db_session):
    """list_users search matches email and name fields."""
    user1 = make_user(email="alice@example.com", first_name="Alice")
    user2 = make_user(email="bob@example.com", first_name="Bob")
    db_session.add_all([user1, user2])
    await db_session.flush()

    service = AdminService(db_session)
    result = await service.list_users(search="alice")

    assert result["count"] == 1
    assert result["items"][0].email == "alice@example.com"


@pytest.mark.asyncio
async def test_update_user_status_creates_audit_log(db_session):
    """update_user_status writes an audit log entry."""
    from app.modules.admin.models import AuditLog

    admin = make_user(role=UserRole.ADMIN.value)
    target = make_user(account_status=AccountStatus.ACTIVE.value)
    db_session.add_all([admin, target])
    await db_session.flush()

    service = AdminService(db_session)
    await service.update_user_status(
        admin_id=admin.id,
        user_id=target.id,
        new_status=AccountStatus.SUSPENDED.value,
    )

    from sqlalchemy import select
    stmt = select(AuditLog).where(AuditLog.target_id == target.id)
    result = await db_session.execute(stmt)
    log_entry = result.scalar_one_or_none()

    assert log_entry is not None
    assert log_entry.action == "UPDATE_USER_STATUS"
    assert log_entry.admin_id == admin.id


@pytest.mark.asyncio
async def test_cannot_modify_admin_user(db_session):
    """update_user_status raises CannotModifyAdminException for admin targets."""
    admin1 = make_user(role=UserRole.ADMIN.value)
    admin2 = make_user(role=UserRole.ADMIN.value)
    db_session.add_all([admin1, admin2])
    await db_session.flush()

    service = AdminService(db_session)
    with pytest.raises(CannotModifyAdminException):
        await service.update_user_status(
            admin_id=admin1.id,
            user_id=admin2.id,
            new_status=AccountStatus.SUSPENDED.value,
        )


@pytest.mark.asyncio
async def test_bulk_update_enforces_limit(db_session):
    """bulk_update_user_status enforces 100-record limit."""
    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()

    service = AdminService(db_session)
    user_ids = [uuid4() for _ in range(101)]

    with pytest.raises(ValidationException, match="limited to 100"):
        await service.bulk_update_user_status(
            admin_id=admin.id,
            user_ids=user_ids,
            action=AccountStatus.SUSPENDED.value,
        )


@pytest.mark.asyncio
async def test_bulk_update_creates_audit_logs_per_record(db_session):
    """bulk_update_user_status writes audit log per updated user."""
    from app.modules.admin.models import AuditLog

    admin = make_user(role=UserRole.ADMIN.value)
    user1 = make_user()
    user2 = make_user()
    db_session.add_all([admin, user1, user2])
    await db_session.flush()

    service = AdminService(db_session)
    result = await service.bulk_update_user_status(
        admin_id=admin.id,
        user_ids=[user1.id, user2.id],
        action=AccountStatus.SUSPENDED.value,
    )

    assert result["updated"] == 2

    from sqlalchemy import select
    stmt = select(AuditLog).where(AuditLog.admin_id == admin.id)
    result = await db_session.execute(stmt)
    logs = result.scalars().all()

    assert len(logs) == 2


@pytest.mark.asyncio
async def test_moderate_job_updates_status_and_logs(db_session):
    """moderate_job updates moderation_status and writes audit log."""
    from app.modules.admin.models import AuditLog
    from app.modules.users.models import EmployerProfile

    admin = make_user(role=UserRole.ADMIN.value)
    employer = make_employer()
    db_session.add_all([admin, employer])
    await db_session.flush()

    profile = EmployerProfile(
        user_id=employer.id,
        company_name="Test Corp",
        industry="Tech",
        company_size="11-50",
        is_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.flush()

    job = make_job(employer.id, moderation_status=ModerationStatus.PENDING.value)
    db_session.add(job)
    await db_session.flush()

    service = AdminService(db_session)
    result = await service.moderate_job(
        admin_id=admin.id,
        job_id=job.id,
        action=ModerationStatus.APPROVED.value,
    )

    assert result.moderation_status == ModerationStatus.APPROVED.value

    from sqlalchemy import select
    stmt = select(AuditLog).where(AuditLog.target_id == job.id)
    audit_result = await db_session.execute(stmt)
    log_entry = audit_result.scalar_one_or_none()

    assert log_entry is not None
    assert log_entry.action == "MODERATE_JOB_APPROVED"


@pytest.mark.asyncio
async def test_job_cannot_publish_without_approval(db_session):
    """Job publish blocked if moderation_status != approved."""
    from app.modules.jobs.enums import JobStatus
    from app.modules.jobs.service import JobService

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(
        employer.id,
        status=JobStatus.DRAFT.value,
        moderation_status=ModerationStatus.PENDING.value,
    )
    db_session.add(job)
    await db_session.flush()

    service = JobService(db_session)
    with pytest.raises(ValidationException, match="approved"):
        await service.publish_job(job.id, current_user=employer)


@pytest.mark.asyncio
async def test_stats_endpoint_returns_correct_counts(db_session):
    """get_platform_stats returns correct aggregate counts for seeded users."""
    from sqlalchemy import func, select

    from app.modules.users.models import User as UserModel

    # Count what's already in the DB before adding our test data
    pre_count = await db_session.execute(select(func.count()).select_from(UserModel))
    pre_total = pre_count.scalar()

    candidate = make_user(role=UserRole.CANDIDATE.value)
    employer = make_employer()
    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add_all([candidate, employer, admin])
    await db_session.flush()

    from app.modules.users.models import EmployerProfile
    profile = EmployerProfile(
        user_id=employer.id,
        company_name="Test",
        industry="Tech",
        company_size="11-50",
        is_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.flush()

    service = AdminService(db_session)
    stats = await service.get_platform_stats()

    # Assert relative to pre-existing data
    assert stats["users"]["total"] == pre_total + 3
    assert stats["users"]["candidates"] >= 1
    assert stats["users"]["employers"] >= 1
    assert stats["users"]["admins"] >= 1


@pytest.mark.asyncio
async def test_csv_export_returns_correct_headers(db_session):
    """export_applications_csv returns CSV with correct headers."""
    service = AdminService(db_session)
    csv_content = await service.export_applications_csv()

    # csv module uses \r\n line endings — strip each field
    first_line = csv_content.splitlines()[0]
    headers = [h.strip() for h in first_line.split(",")]

    expected_headers = [
        "application_id",
        "candidate_name",
        "candidate_email",
        "job_title",
        "company_name",
        "status",
        "applied_date",
        "status_updated_date",
    ]

    assert headers == expected_headers


@pytest.mark.asyncio
async def test_audit_log_returns_entries_in_reverse_chronological(db_session):
    """list_audit_log returns entries newest first."""
    from datetime import UTC, datetime, timedelta

    from app.modules.admin.models import AuditLog

    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()

    now = datetime.now(UTC)

    log1 = AuditLog(
        admin_id=admin.id,
        action="ACTION_1",
        target_type="user",
        target_id=uuid4(),
        log_metadata={},
        created_at=now - timedelta(seconds=10),  # older
    )
    log2 = AuditLog(
        admin_id=admin.id,
        action="ACTION_2",
        target_type="user",
        target_id=uuid4(),
        log_metadata={},
        created_at=now,  # newer
    )
    db_session.add_all([log1, log2])
    await db_session.flush()

    service = AdminService(db_session)
    result = await service.list_audit_log()

    actions = [e.action for e in result["items"]]
    assert actions.index("ACTION_2") < actions.index("ACTION_1")


@pytest.mark.asyncio
async def test_get_user_detail_raises_for_unknown(db_session):
    """get_user_detail raises UserNotFoundException for unknown ID."""
    service = AdminService(db_session)

    with pytest.raises(UserNotFoundException):
        await service.get_user_detail(user_id=uuid4())


@pytest.mark.asyncio
async def test_moderate_job_raises_for_unknown(db_session):
    """moderate_job raises JobNotFoundError for unknown ID."""
    admin = make_user(role=UserRole.ADMIN.value)
    db_session.add(admin)
    await db_session.flush()

    service = AdminService(db_session)

    with pytest.raises(JobNotFoundError):
        await service.moderate_job(
            admin_id=admin.id,
            job_id=uuid4(),
            action=ModerationStatus.APPROVED.value,
        )
