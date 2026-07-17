"""Tests for the job posting gate — employer profile completeness check.

Covers:
- Employer with incomplete profile cannot post a job (403)
- Employer with complete profile can post a job (201)
- Gate is enforced at the service layer via create_job
"""

import pytest

from app.core.exceptions import PermissionDeniedException
from app.modules.jobs.enums import ContractType, WorkModel
from app.modules.jobs.schemas import JobCreateRequest
from app.modules.jobs.service import JobService
from app.modules.users.models import EmployerProfile


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


async def create_employer_with_profile(db_session, is_complete: bool):
    """Create an employer user with an EmployerProfile set to the given completeness."""
    from tests.conftest import make_employer

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    profile = EmployerProfile(
        user_id=employer.id,
        company_name="Acme Corp" if is_complete else None,
        industry="Technology" if is_complete else None,
        is_profile_complete=is_complete,
    )
    db_session.add(profile)
    await db_session.flush()

    # Reload employer so the relationship is populated
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.modules.users.models import User

    result = await db_session.execute(
        select(User)
        .where(User.id == employer.id)
        .options(selectinload(User.employer_profile))
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
    """create_job succeeds when employer profile is complete."""
    employer = await create_employer_with_profile(db_session, is_complete=True)

    service = JobService(db_session)
    result = await service.create_job(make_create_request(), employer=employer)

    assert result.employer_id == employer.id


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

    profile = EmployerProfile(
        user_id=user.id,
        is_profile_complete=False,
    )
    db_session.add(profile)
    await db_session.flush()

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

    profile = EmployerProfile(
        user_id=user.id,
        company_name="Acme Corp",
        industry="Technology",
        is_profile_complete=True,
    )
    db_session.add(profile)
    await db_session.flush()

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
