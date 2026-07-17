"""Integration tests for the applications module — full HTTP stack."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.storage import MockStorageService, get_storage_service
from app.main import app
from app.modules.applications.enums import ApplicationStatus
from app.modules.applications.models import Application
from app.modules.jobs.enums import ContractType, WorkModel
from app.modules.users.models import EmployerProfile, User
from tests.conftest import make_register_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def future_deadline(days: int = 7) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def past_deadline(days: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def job_payload(**overrides) -> dict:
    defaults = {
        "title": "Backend Engineer",
        "about_the_role": "Build scalable APIs for a growing platform.",
        "key_responsibilities": "Design, build and maintain backend services.",
        "requirements": "Strong Python skills and experience with FastAPI.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "work_location": "LOCAL",
        "application_deadline": future_deadline(),
    }
    defaults.update(overrides)
    return defaults


async def register_and_activate(
    client, db_session, role: str = "CANDIDATE"
) -> tuple[str, User]:
    """Register a user, activate them, return (access_token, user)."""
    from app.modules.auth.jwt_handler import create_token_pair

    data = make_register_data(role="CANDIDATE")
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
        "role": "CANDIDATE",
    }
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201

    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = role
    user.account_status = "ACTIVE"
    await db_session.flush()

    if role == "EMPLOYER":
        profile = EmployerProfile(
            user_id=user.id,
            company_name="Test Corp",
            industry="Technology",
            company_size="11-50",
            is_profile_complete=True,
        )
        db_session.add(profile)
        await db_session.flush()

    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"], user


async def create_job_via_api(
    client, db_session, employer_token: str, **overrides
) -> dict:
    """Create a job, approve it via admin, then publish it. Returns the job response dict."""
    resp = await client.post(
        "/api/v1/jobs",
        json=job_payload(**overrides),
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()

    # Create a real admin user and approve the job (required since moderation defaults to PENDING)
    admin_token, _ = await register_and_activate(client, db_session, "ADMIN")
    approve = await client.patch(
        f"/api/v1/admin/jobs/{job['id']}/moderate",
        json={"action": "APPROVED"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approve.status_code == 200, approve.text

    pub = await client.post(
        f"/api/v1/jobs/{job['id']}/publish",
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert pub.status_code == 200, pub.text
    return pub.json()


async def upload_cv(client, candidate_token: str) -> None:
    """Upload a minimal PDF CV for the candidate."""
    pdf_bytes = b"%PDF-1.4 fake pdf content for testing"
    await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )


async def complete_candidate_profile(client, db_session, token: str, user_id) -> None:
    """Set required profile fields and upload a CV so is_profile_complete=True."""
    from app.modules.candidates.models import CandidateProfile

    await client.put(
        "/api/v1/candidates/me",
        json={
            "bio": "Experienced software developer.",
            "skills": ["Python", "FastAPI", "PostgreSQL"],
            "years_of_experience": 3,
            "location": "Lagos, Nigeria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    await upload_cv(client, token)
    # Force flag in DB — CV upload triggers recompute but test session may not see it
    result = await db_session.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    if profile:
        profile.is_profile_complete = True
        await db_session.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_storage():
    app.dependency_overrides[get_storage_service] = lambda: MockStorageService()
    yield
    app.dependency_overrides.pop(get_storage_service, None)


# ---------------------------------------------------------------------------
# Apply to job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_candidate_applies_successfully(client, db_session):
    """POST /applications creates an application row with status submitted."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == ApplicationStatus.SUBMITTED.value
    assert body["job_id"] == job["id"]

    result = await db_session.execute(
        select(Application).where(Application.candidate_id == candidate_user.id)
    )
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_duplicate_application_returns_409(client, db_session):
    """Applying to the same job twice returns 409."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "ALREADY_APPLIED"


@pytest.mark.asyncio
async def test_apply_to_expired_job_returns_error(client, db_session):
    """Applying to a job with a past deadline returns the correct error."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(
        client, db_session, employer_token, application_deadline=past_deadline()
    )

    resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "JOB_DEADLINE_PAST"


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_withdraw_from_submitted_succeeds(client, db_session):
    """PATCH /applications/{id}/withdraw from submitted status succeeds."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    apply_resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert apply_resp.status_code == 201, apply_resp.text
    application_id = apply_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/applications/{application_id}/withdraw",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == ApplicationStatus.WITHDRAWN.value


@pytest.mark.asyncio
async def test_withdraw_from_shortlisted_returns_error(client, db_session):
    """PATCH /applications/{id}/withdraw from shortlisted status is rejected."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    apply_resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    application_id = apply_resp.json()["id"]

    # Advance to shortlisted
    await client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"new_status": ApplicationStatus.REVIEWING.value},
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    await client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"new_status": ApplicationStatus.SHORTLISTED.value},
        headers={"Authorization": f"Bearer {employer_token}"},
    )

    resp = await client.patch(
        f"/api/v1/applications/{application_id}/withdraw",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "WITHDRAWAL_ERROR"


# ---------------------------------------------------------------------------
# Employer applicant list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_employer_views_own_job_applicants(client, db_session):
    """GET /applications/job/{id} returns applicants for the employer's own job."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )

    resp = await client.get(
        f"/api/v1/applications/job/{job['id']}",
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


@pytest.mark.asyncio
async def test_employer_cannot_view_other_employers_applicants(client, db_session):
    """GET /applications/job/{id} returns 403 for a different employer."""
    employer1_token, _ = await register_and_activate(client, db_session, "EMPLOYER")
    employer2_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    job = await create_job_via_api(client, db_session, employer1_token)

    resp = await client.get(
        f"/api/v1/applications/job/{job['id']}",
        headers={"Authorization": f"Bearer {employer2_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valid_status_transition_records_updated_at(client, db_session):
    """PATCH /applications/{id}/status records status_updated_at and status_updated_by."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, employer_user = await register_and_activate(
        client, db_session, "EMPLOYER"
    )

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    apply_resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    application_id = apply_resp.json()["id"]

    resp = await client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"new_status": ApplicationStatus.REVIEWING.value},
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == ApplicationStatus.REVIEWING.value

    # Expire cached state so we get fresh data from DB
    await db_session.execute(select(Application))
    result = await db_session.execute(
        select(Application).where(Application.id == application_id)
    )
    app_row = result.scalar_one()
    assert app_row.status_updated_by == employer_user.id
    assert app_row.status_updated_at is not None


@pytest.mark.asyncio
async def test_invalid_status_transition_returns_error(client, db_session):
    """PATCH /applications/{id}/status with invalid transition returns domain error."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    apply_resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    application_id = apply_resp.json()["id"]

    # submitted → hired is not a valid transition
    resp = await client.patch(
        f"/api/v1/applications/{application_id}/status",
        json={"new_status": ApplicationStatus.HIRED.value},
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == "INVALID_STATUS_TRANSITION"


# ---------------------------------------------------------------------------
# has_applied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_applied_returns_false_before_applying(client, db_session):
    """GET /applications/{job_id}/has-applied returns false before applying."""
    candidate_token, _ = await register_and_activate(client, db_session, "CANDIDATE")
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    job = await create_job_via_api(client, db_session, employer_token)

    resp = await client.get(
        f"/api/v1/applications/{job['id']}/has-applied",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["has_applied"] is False


@pytest.mark.asyncio
async def test_has_applied_returns_true_after_applying(client, db_session):
    """GET /applications/{job_id}/has-applied returns true after applying."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(client, db_session, employer_token)

    await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )

    resp = await client.get(
        f"/api/v1/applications/{job['id']}/has-applied",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["has_applied"] is True


# ---------------------------------------------------------------------------
# My applications — job context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_applications_includes_job_context(client, db_session):
    """GET /applications/me includes job_title and company_name in each item."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_job_via_api(
        client, db_session, employer_token, title="Senior Python Developer"
    )

    await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )

    resp = await client.get(
        "/api/v1/applications/me",
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["job_title"] == "Senior Python Developer"
    assert items[0]["company_name"] == "Test Corp"
