"""The job review flow: admins are told when a job waits for review, and an employer can ask for
the job to be published the moment it is approved.

Before, nobody was told: a new job sat as a draft until an admin happened to open the Jobs page,
and after approval the employer had to come back and press Publish."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.modules.admin.service import AdminService
from app.modules.ai import tasks as ai_tasks
from app.modules.applications import tasks as application_tasks
from app.modules.jobs.enums import ContractType, JobStatus, WorkModel
from app.modules.jobs.schemas import JobCreateRequest, JobUpdateRequest
from app.modules.jobs.service import JobService
from app.modules.notifications.models import Notification
from app.modules.users.models import User
from tests.conftest import (
    make_admin,
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)
    monkeypatch.setattr(ai_tasks.score_job_against_talent_pool_task, "delay", MagicMock())
    monkeypatch.setattr(ai_tasks.generate_job_embedding_task, "delay", MagicMock())


@pytest.fixture
def moderation_emails(monkeypatch):
    queued = MagicMock()
    monkeypatch.setattr(application_tasks.send_job_moderation_email, "delay", queued)
    return queued


def _request(**overrides) -> JobCreateRequest:
    defaults = {
        "title": "Senior Engineer",
        "about_the_role": "Build great things at scale.",
        "key_responsibilities": "Design, build and maintain backend services.",
        "requirements": "Strong Python skills and experience with FastAPI.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME,
        "work_model": WorkModel.HYBRID,
        "work_location": "LOCAL",
    }
    defaults.update(overrides)
    return JobCreateRequest(**defaults)


async def _employer(db_session, plan=None):
    """A verified employer with a complete company profile, loaded the way a request has it."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(
        db_session,
        employer,
        company_name="Acme Corp",
        industry="Technology",
        is_profile_complete=True,
        kyc_status="APPROVED",
    )
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    result = await db_session.execute(
        select(User).where(User.id == employer.id).options(selectinload(User.organization))
    )
    return result.scalar_one()


async def _admin(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    return admin


async def _waiting_notices_for(db_session, user, job_id=None):
    stmt = select(Notification).where(
        Notification.recipient_id == user.id, Notification.type == "JOB_AWAITING_REVIEW"
    )
    if job_id is not None:
        stmt = stmt.where(Notification.entity_id == job_id)
    return (await db_session.execute(stmt)).scalars().all()


async def _pending_job(db_session, owner, **overrides):
    overrides.setdefault("status", JobStatus.DRAFT.value)
    overrides.setdefault("moderation_status", "PENDING")
    job = make_job(owner.id, **overrides)
    db_session.add(job)
    await db_session.flush()
    return job


# --- admins are told -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_employer_job_tells_the_admins_it_is_waiting(db_session):
    employer = await _employer(db_session)
    admin = await _admin(db_session)

    created = await JobService(db_session).create_job(_request(), employer=employer)

    notices = await _waiting_notices_for(db_session, admin, created.id)
    assert len(notices) == 1
    assert notices[0].title == "Acme Corp posted a job: Senior Engineer"
    assert "approve it or ask for changes" in notices[0].body
    assert notices[0].entity_type == "JOB"
    assert await _waiting_notices_for(db_session, employer) == []  # the employer is not told


@pytest.mark.asyncio
async def test_a_job_an_admin_posts_waits_for_no_one(db_session):
    admin = await _admin(db_session)

    created = await JobService(db_session).create_job(_request(), employer=admin)

    assert await _waiting_notices_for(db_session, admin, created.id) == []


@pytest.mark.asyncio
async def test_a_rejected_job_sent_back_for_review_tells_the_admins_again(db_session):
    employer = await _employer(db_session)
    admin = await _admin(db_session)
    job = make_job(
        employer.id, status=JobStatus.DRAFT.value, moderation_status="REJECTED"
    )
    db_session.add(job)
    await db_session.flush()

    await JobService(db_session).resubmit_job(job.id, employer)

    notices = await _waiting_notices_for(db_session, admin, job.id)
    assert len(notices) == 1
    assert "sent a job back for review" in notices[0].title


@pytest.mark.asyncio
async def test_editing_a_live_job_pulls_it_offline_and_tells_the_admins(db_session):
    employer = await _employer(db_session)
    admin = await _admin(db_session)
    job = make_job(
        employer.id,
        status=JobStatus.ACTIVE.value,
        moderation_status="APPROVED",
        published_at=datetime.now(UTC),
    )
    db_session.add(job)
    await db_session.flush()

    await JobService(db_session).update_job(
        job.id, JobUpdateRequest(about_the_role="A completely different role."), employer
    )

    notices = await _waiting_notices_for(db_session, admin, job.id)
    assert len(notices) == 1
    assert "needs review again" in notices[0].title


@pytest.mark.asyncio
async def test_changing_the_publish_choice_on_a_live_job_does_not_pull_it_offline(db_session):
    """It is a private preference, not part of the public listing, like the interview brief."""
    employer = await _employer(db_session)
    admin = await _admin(db_session)
    job = make_job(
        employer.id,
        status=JobStatus.ACTIVE.value,
        moderation_status="APPROVED",
        published_at=datetime.now(UTC),
    )
    db_session.add(job)
    await db_session.flush()

    updated = await JobService(db_session).update_job(
        job.id, JobUpdateRequest(publish_when_approved=True), employer
    )

    assert updated.status == "ACTIVE"
    assert updated.publish_when_approved is True
    assert await _waiting_notices_for(db_session, admin, job.id) == []


@pytest.mark.asyncio
async def test_changing_what_candidates_see_on_a_live_job_does_send_it_for_review(db_session):
    employer = await _employer(db_session)
    job = make_job(
        employer.id,
        status=JobStatus.ACTIVE.value,
        moderation_status="APPROVED",
        published_at=datetime.now(UTC),
        openings_count=1,
    )
    db_session.add(job)
    await db_session.flush()

    updated = await JobService(db_session).update_job(
        job.id, JobUpdateRequest(openings_count=2), employer
    )

    assert updated.status == "DRAFT"  # pulled offline for review, as before


# --- publish as soon as approved -----------------------------------------------------------


@pytest.mark.asyncio
async def test_the_choice_is_saved_and_defaults_to_off(db_session):
    employer = await _employer(db_session)

    plain = await JobService(db_session).create_job(_request(), employer=employer)
    asked = await JobService(db_session).create_job(
        _request(title="Another", publish_when_approved=True), employer=employer
    )

    assert plain.publish_when_approved is False
    assert asked.publish_when_approved is True


@pytest.mark.asyncio
async def test_an_approved_job_is_published_at_once_when_the_employer_asked_for_that(
    db_session, moderation_emails
):
    employer = await _employer(db_session, plan="professional")
    admin = await _admin(db_session)
    job = await _pending_job(db_session, employer, publish_when_approved=True)

    approved = await AdminService(db_session).moderate_job(admin.id, job.id, "APPROVED")

    assert approved.status == "ACTIVE"
    await db_session.refresh(job)
    assert job.published_at is not None
    moderation_emails.assert_called_once_with(
        employer.email, str(job.id), job.title, "APPROVED_AND_PUBLISHED", None
    )


@pytest.mark.asyncio
async def test_without_the_choice_an_approved_job_stays_a_draft_as_before(
    db_session, moderation_emails
):
    employer = await _employer(db_session, plan="professional")
    admin = await _admin(db_session)
    job = await _pending_job(db_session, employer)

    approved = await AdminService(db_session).moderate_job(admin.id, job.id, "APPROVED")

    assert approved.status == "DRAFT"
    moderation_emails.assert_called_once_with(
        employer.email, str(job.id), job.title, "APPROVED", None
    )


@pytest.mark.asyncio
async def test_a_job_the_plan_does_not_allow_yet_stays_approved_and_the_employer_is_told_why(
    db_session, moderation_emails
):
    """A Starter company that has already published this month: the approval must stand, the
    job must not go live, and the email must say why. A refused publish must never undo the
    approval itself."""
    employer = await _employer(db_session)  # Starter
    admin = await _admin(db_session)
    await _pending_job(  # last published today, so this month's one slot is used
        db_session, employer, status=JobStatus.CLOSED.value, published_at=datetime.now(UTC)
    )
    job = await _pending_job(db_session, employer, title="Waiting", publish_when_approved=True)

    approved = await AdminService(db_session).moderate_job(admin.id, job.id, "APPROVED")

    assert approved.status == "DRAFT"
    await db_session.refresh(job)
    assert job.moderation_status == "APPROVED"  # the approval stands
    [call] = moderation_emails.call_args_list
    assert call.args[3] == "APPROVED_NOT_PUBLISHED"
    assert "one new job a month" in call.args[4]


@pytest.mark.asyncio
async def test_a_rejection_never_publishes_even_if_the_employer_asked(db_session, moderation_emails):
    employer = await _employer(db_session, plan="professional")
    admin = await _admin(db_session)
    job = await _pending_job(db_session, employer, publish_when_approved=True)

    rejected = await AdminService(db_session).moderate_job(
        admin.id, job.id, "REJECTED", "The salary is missing."
    )

    assert rejected.status == "DRAFT"
    moderation_emails.assert_called_once_with(
        employer.email, str(job.id), job.title, "REJECTED", "The salary is missing."
    )


@pytest.mark.asyncio
async def test_the_audit_log_still_records_the_approval(db_session, moderation_emails):
    from app.modules.admin.models import AuditLog

    employer = await _employer(db_session, plan="professional")
    admin = await _admin(db_session)
    job = await _pending_job(db_session, employer, publish_when_approved=True)

    await AdminService(db_session).moderate_job(admin.id, job.id, "APPROVED")

    entries = (
        await db_session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.admin_id == admin.id, AuditLog.action == "MODERATE_JOB_APPROVED")
        )
    ).scalar_one()
    assert entries == 1
