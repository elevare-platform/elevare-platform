"""Tests for the job posting gate — employer profile completeness + KYC checks.

Covers:
- Employer with incomplete profile cannot post a job (403)
- Employer with complete profile and approved KYC can post a job (201)
- Employer with complete profile but unapproved KYC cannot post a job (403)
- Gate is enforced at the service layer via create_job
"""

import pytest

from app.core.exceptions import KYCRequiredException, PermissionDeniedException
from app.modules.jobs.enums import ContractType, WorkModel
from app.modules.jobs.schemas import JobCreateRequest
from app.modules.jobs.service import JobService


def make_create_request(**overrides) -> JobCreateRequest:
    """Build a JobCreateRequest with sensible defaults."""
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


async def create_employer_with_profile(
    db_session, is_complete: bool, kyc_status: str = "APPROVED"
):
    """Create an employer user with an Organization set to the given completeness."""
    from tests.conftest import make_employer, make_organization_for

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    await make_organization_for(
        db_session,
        employer,
        company_name="Acme Corp" if is_complete else None,
        industry="Technology" if is_complete else None,
        is_profile_complete=is_complete,
        kyc_status=kyc_status,
    )

    # Reload employer so the relationship is populated
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.modules.users.models import User

    result = await db_session.execute(
        select(User)
        .where(User.id == employer.id)
        .options(selectinload(User.organization))
    )
    return result.scalar_one()


# ---------------------------------------------------------------------------
# Service-layer tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_job_blocked_for_incomplete_profile(db_session):
    """create_job raises PermissionDeniedException when employer profile is incomplete."""
    employer = await create_employer_with_profile(db_session, is_complete=False)

    service = JobService(db_session)
    with pytest.raises(PermissionDeniedException) as exc_info:
        await service.create_job(make_create_request(), employer=employer)

    assert "profile" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_create_job_allowed_for_complete_profile(db_session):
    """create_job succeeds when employer profile is complete and KYC is approved."""
    employer = await create_employer_with_profile(db_session, is_complete=True)

    service = JobService(db_session)
    result = await service.create_job(make_create_request(), employer=employer)

    assert result.employer_id == employer.id


@pytest.mark.parametrize("kyc_status", ["NOT_SUBMITTED", "PENDING", "REJECTED"])
@pytest.mark.asyncio
async def test_create_job_blocked_when_kyc_not_approved(db_session, kyc_status):
    """create_job raises KYCRequiredException when profile is complete but KYC isn't approved."""
    employer = await create_employer_with_profile(
        db_session, is_complete=True, kyc_status=kyc_status
    )

    service = JobService(db_session)
    with pytest.raises(KYCRequiredException):
        await service.create_job(make_create_request(), employer=employer)


@pytest.mark.parametrize("kyc_status", ["NOT_SUBMITTED", "PENDING", "REJECTED"])
@pytest.mark.asyncio
async def test_create_job_allowed_when_kyc_enforcement_disabled(
    db_session, kyc_status, monkeypatch
):
    """The KYC_ENFORCEMENT_ENABLED=False escape hatch (HR-requested) lets an
    employer post regardless of kyc_status — profile-completeness is
    unaffected by this flag and still applies.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "kyc_enforcement_enabled", False)
    employer = await create_employer_with_profile(
        db_session, is_complete=True, kyc_status=kyc_status
    )

    service = JobService(db_session)
    result = await service.create_job(make_create_request(), employer=employer)

    assert result.employer_id == employer.id


@pytest.mark.asyncio
async def test_create_job_still_blocked_by_profile_completeness_when_kyc_disabled(
    db_session, monkeypatch
):
    """KYC_ENFORCEMENT_ENABLED=False only skips the KYC check — an incomplete
    profile is still blocked, since that's a separate, unrelated gate.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "kyc_enforcement_enabled", False)
    employer = await create_employer_with_profile(db_session, is_complete=False)

    service = JobService(db_session)
    with pytest.raises(PermissionDeniedException):
        await service.create_job(make_create_request(), employer=employer)


@pytest.mark.asyncio
async def test_create_job_blocked_when_no_employer_profile_exists(db_session):
    """create_job raises PermissionDeniedException when employer has no EmployerProfile row.

    The gate blocks posting when there is no profile at all — the employer must
    complete onboarding before posting jobs.
    """
    from tests.conftest import make_employer

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    # No EmployerProfile created
    service = JobService(db_session)
    with pytest.raises(PermissionDeniedException) as exc_info:
        await service.create_job(make_create_request(), employer=employer)

    assert "profile" in exc_info.value.message.lower()


# ---------------------------------------------------------------------------
# HTTP integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_job_returns_403_for_incomplete_profile(client, db_session):
    """POST /jobs returns 403 PERMISSION_DENIED when employer profile is incomplete."""
    from sqlalchemy import select

    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import User
    from tests.conftest import make_register_data

    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = "EMPLOYER"
    user.account_status = "ACTIVE"
    await db_session.flush()

    from tests.conftest import make_organization_for

    await make_organization_for(
        db_session,
        user,
        is_profile_complete=False,
    )

    token_pair = create_token_pair(user.id, "EMPLOYER")
    token = token_pair["access_token"]

    response = await client.post(
        "/api/v1/jobs",
        json={
            "title": "Engineer",
            "about_the_role": "Build things at scale.",
            "key_responsibilities": "Design and build services.",
            "requirements": "Python and FastAPI experience.",
            "location": "Lagos",
            "contract_type": ContractType.FULL_TIME.value,
            "work_model": WorkModel.HYBRID.value,
            "work_location": "LOCAL",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_post_job_succeeds_for_complete_profile(client, db_session):
    """POST /jobs returns 201 when employer profile is complete."""
    from sqlalchemy import select

    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import User
    from tests.conftest import make_register_data

    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = "EMPLOYER"
    user.account_status = "ACTIVE"
    await db_session.flush()

    from tests.conftest import make_organization_for

    await make_organization_for(
        db_session,
        user,
        company_name="Acme Corp",
        industry="Technology",
        is_profile_complete=True,
        kyc_status="APPROVED",
    )

    token_pair = create_token_pair(user.id, "EMPLOYER")
    token = token_pair["access_token"]

    response = await client.post(
        "/api/v1/jobs",
        json={
            "title": "Engineer",
            "about_the_role": "Build things at scale.",
            "key_responsibilities": "Design and build services.",
            "requirements": "Python and FastAPI experience.",
            "location": "Lagos",
            "contract_type": ContractType.FULL_TIME.value,
            "work_model": WorkModel.HYBRID.value,
            "work_location": "LOCAL",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_post_job_returns_403_for_unapproved_kyc(client, db_session):
    """POST /jobs returns 403 KYC_REQUIRED when profile is complete but KYC isn't approved."""
    from sqlalchemy import select

    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import User
    from tests.conftest import make_register_data

    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = "EMPLOYER"
    user.account_status = "ACTIVE"
    await db_session.flush()

    from tests.conftest import make_organization_for

    await make_organization_for(
        db_session,
        user,
        company_name="Acme Corp",
        industry="Technology",
        is_profile_complete=True,
        kyc_status="PENDING",
    )

    token_pair = create_token_pair(user.id, "EMPLOYER")
    token = token_pair["access_token"]

    response = await client.post(
        "/api/v1/jobs",
        json={
            "title": "Engineer",
            "about_the_role": "Build things at scale.",
            "key_responsibilities": "Design and build services.",
            "requirements": "Python and FastAPI experience.",
            "location": "Lagos",
            "contract_type": ContractType.FULL_TIME.value,
            "work_model": WorkModel.HYBRID.value,
            "work_location": "LOCAL",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "KYC_REQUIRED"


# ---------------------------------------------------------------------------
# Publish-time quota gate (Starter plan, 1 active job posting)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_blocked_when_starter_quota_already_used(client, db_session):
    """A second job can't be published on Starter once the first is ACTIVE.

    Reproduces a real bug report: the frontend surfaced a generic "failed to
    publish" message instead of the real quota-exceeded reason. This locks
    in the backend side (a real, useful `message`) so a regression there
    would fail loudly instead of only being noticed by a confused employer.
    """
    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.jobs.enums import JobStatus
    from tests.conftest import make_employer, make_job, make_organization_for

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    await make_organization_for(
        db_session,
        employer,
        company_name="Test Corp",
        industry="Technology",
        company_size="1-10",
        is_profile_complete=True,
        kyc_status="APPROVED",
    )

    # Quota-filling job: already ACTIVE, counts against the Starter limit of 1.
    active_job = make_job(
        employer.id, status=JobStatus.ACTIVE.value, moderation_status="APPROVED"
    )
    db_session.add(active_job)
    # The job actually under test: DRAFT + APPROVED, ready to publish.
    draft_job = make_job(
        employer.id, status=JobStatus.DRAFT.value, moderation_status="APPROVED"
    )
    db_session.add(draft_job)
    await db_session.flush()

    token = create_token_pair(employer.id, "EMPLOYER")["access_token"]

    response = await client.post(
        f"/api/v1/jobs/{draft_job.id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["code"] == "JOB_POSTING_LIMIT_EXCEEDED"
    # The frontend reads this exact field to show the employer why — must
    # stay a real, specific sentence, not a generic fallback.
    assert "plan allows" in body["message"].lower()
