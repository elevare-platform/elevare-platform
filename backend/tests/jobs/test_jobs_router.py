"""Integration tests for job endpoints — full HTTP stack."""

import pytest

from app.modules.jobs.enums import ContractType, JobStatus, WorkModel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def job_payload(**overrides) -> dict:
    """Return a valid job creation JSON payload with sensible defaults."""
    defaults = {
        "title": "Backend Engineer",
        "description": "Build scalable APIs for our growing platform.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "work_location": "LOCAL",
        "salary_min": 500000,
        "salary_max": 900000,
    }
    defaults.update(overrides)
    return defaults


async def register_employer(client) -> tuple[str, dict]:
    """Register an employer and return (access_token, payload)."""
    from tests.conftest import make_register_data

    data = make_register_data()
    payload = {
        "first_name": data.first_name,
        "last_name": data.last_name,
        "email": data.email,
        "phone_number": data.phone_number,
        "password": data.password,
        "confirm_password": data.confirm_password,
    }
    reg = await client.post("/api/v1/auth/register", json=payload)
    assert reg.status_code == 201

    # Manually set role to EMPLOYER via DB — registration defaults to CANDIDATE
    # In tests we patch the user role directly through the service
    token = reg.json()["access_token"]
    return token, payload


async def register_and_promote(client, db_session, role: str) -> str:
    """Register a user, promote them to the given role, and return an access token.

    For EMPLOYER role, also creates a complete EmployerProfile so the job
    posting gate is satisfied.
    """
    from sqlalchemy import select

    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import EmployerProfile, User
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

    # Promote role directly in DB
    result = await db_session.execute(select(User).where(User.email == data.email))
    user = result.scalar_one()
    user.role = role
    user.account_status = "ACTIVE"
    await db_session.flush()

    # Employers need a complete profile to pass the job posting gate
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

    # Issue a fresh token with the updated role — avoids a login round-trip
    # that would fail if account_status enforcement is strict on login
    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"]


# ---------------------------------------------------------------------------
# Public listing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_jobs_returns_active_only(client, db_session):
    """GET /jobs returns only ACTIVE jobs."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    active = make_job(employer.id, status=JobStatus.ACTIVE.value)
    draft = make_job(employer.id, status=JobStatus.DRAFT.value, title="Draft Job")
    closed = make_job(employer.id, status=JobStatus.CLOSED.value, title="Closed Job")
    db_session.add_all([active, draft, closed])
    await db_session.flush()

    response = await client.get("/api/v1/jobs")
    assert response.status_code == 200
    titles = [j["title"] for j in response.json()["items"]]
    assert active.title in titles
    assert "Draft Job" not in titles
    assert "Closed Job" not in titles


@pytest.mark.asyncio
async def test_list_jobs_filter_by_contract_type(client, db_session):
    """GET /jobs?contract_type=FULL_TIME returns only full-time jobs."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    ft = make_job(
        employer.id, contract_type=ContractType.FULL_TIME.value, title="Full Time Job"
    )
    pt = make_job(
        employer.id, contract_type=ContractType.PART_TIME.value, title="Part Time Job"
    )
    db_session.add_all([ft, pt])
    await db_session.flush()

    response = await client.get("/api/v1/jobs?contract_type=FULL_TIME")
    assert response.status_code == 200
    titles = [j["title"] for j in response.json()["items"]]
    assert "Full Time Job" in titles
    assert "Part Time Job" not in titles


@pytest.mark.asyncio
async def test_get_single_job(client, db_session):
    """GET /jobs/{id} returns the job."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    response = await client.get(f"/api/v1/jobs/{job.id}")
    assert response.status_code == 200
    assert response.json()["id"] == str(job.id)


@pytest.mark.asyncio
async def test_get_nonexistent_job_returns_404(client):
    """GET /jobs/{id} with unknown ID returns 404."""
    from uuid import uuid4

    response = await client.get(f"/api/v1/jobs/{uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cursor pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_cursor_pagination_no_overlap(client, db_session):
    """Cursor pagination returns non-overlapping pages and null cursor on last page."""
    from tests.conftest import make_employer, make_job

    # Dedicated employer — test is fully isolated from other jobs in the DB
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    # Promote to EMPLOYER role so /jobs/mine works
    employer.role = "EMPLOYER"
    await db_session.flush()

    # Create exactly 5 active jobs owned by this employer
    jobs = [make_job(employer.id, title=f"Pagination Job {i}") for i in range(5)]
    db_session.add_all(jobs)
    await db_session.flush()

    # Get a token for this employer
    from app.modules.auth.jwt_handler import create_token_pair

    token_pair = create_token_pair(employer.id, employer.role)
    token = token_pair["access_token"]

    # Page 1 — limit 3 from employer's own jobs (fully isolated)
    r1 = await client.get(
        "/api/v1/jobs/mine?limit=3",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    body1 = r1.json()
    assert len(body1["items"]) == 3
    assert body1["next_cursor"] is not None  # 5 jobs, page size 3 → more exist

    # Page 2 — use cursor from page 1
    r2 = await client.get(
        f"/api/v1/jobs/mine?limit=3&cursor={body1['next_cursor']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert len(body2["items"]) == 2  # 5 total, 3 on page 1 → 2 remain

    # No overlap between pages
    ids1 = {j["id"] for j in body1["items"]}
    ids2 = {j["id"] for j in body2["items"]}
    assert ids1.isdisjoint(ids2), "Pages must not overlap"

    # Last page — next_cursor must be null (only 2 items remain, less than limit of 3)
    assert body2["next_cursor"] is None, "Last page must return null next_cursor"


# ---------------------------------------------------------------------------
# Create job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_job_as_employer(client, db_session):
    """POST /jobs as employer creates a draft job."""
    token = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.post(
        "/api/v1/jobs",
        json=job_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == JobStatus.DRAFT.value


@pytest.mark.asyncio
async def test_create_job_as_candidate_returns_403(client, db_session):
    """POST /jobs as candidate returns 403."""
    token = await register_and_promote(client, db_session, "CANDIDATE")

    response = await client.post(
        "/api/v1/jobs",
        json=job_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Update job
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_own_job(client, db_session):
    """PATCH /jobs/{id} by owning employer updates the job."""
    token = await register_and_promote(client, db_session, "EMPLOYER")

    created = await client.post(
        "/api/v1/jobs",
        json=job_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/jobs/{job_id}",
        json={"title": "Updated Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_update_other_employers_job_returns_403(client, db_session):
    """PATCH /jobs/{id} by a different employer returns 403."""
    token1 = await register_and_promote(client, db_session, "EMPLOYER")
    token2 = await register_and_promote(client, db_session, "EMPLOYER")

    created = await client.post(
        "/api/v1/jobs",
        json=job_payload(),
        headers={"Authorization": f"Bearer {token1}"},
    )
    job_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/jobs/{job_id}",
        json={"title": "Stolen Update"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_job(client, db_session):
    """POST /jobs/{id}/publish transitions DRAFT → ACTIVE."""
    from uuid import UUID

    from app.modules.jobs.models import Job

    token = await register_and_promote(client, db_session, "EMPLOYER")

    created = await client.post(
        "/api/v1/jobs",
        json=job_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = created.json()["id"]
    assert created.json()["status"] == "DRAFT"

    # Approve the job (simulating admin moderation) so publish is allowed
    from sqlalchemy import select

    result = await db_session.execute(select(Job).where(Job.id == UUID(job_id)))
    job = result.scalar_one()
    job.moderation_status = "APPROVED"
    await db_session.flush()

    response = await client.post(
        f"/api/v1/jobs/{job_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_invalid_transition_returns_422(client, db_session):
    """Publishing an already ACTIVE job returns 422."""
    from uuid import UUID

    from sqlalchemy import select

    from app.modules.jobs.models import Job

    token = await register_and_promote(client, db_session, "EMPLOYER")

    created = await client.post(
        "/api/v1/jobs",
        json=job_payload(),
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = created.json()["id"]

    # Approve the job so first publish succeeds
    result = await db_session.execute(select(Job).where(Job.id == UUID(job_id)))
    job = result.scalar_one()
    job.moderation_status = "APPROVED"
    await db_session.flush()

    # Publish once — valid
    await client.post(
        f"/api/v1/jobs/{job_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )

    # Publish again — invalid transition ACTIVE → ACTIVE
    response = await client.post(
        f"/api/v1/jobs/{job_id}/publish",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Employer's own jobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_mine_returns_only_own_jobs(client, db_session):
    """GET /jobs/mine returns only the authenticated employer's jobs."""
    token1 = await register_and_promote(client, db_session, "EMPLOYER")
    token2 = await register_and_promote(client, db_session, "EMPLOYER")

    await client.post(
        "/api/v1/jobs",
        json=job_payload(title="Employer 1 Job"),
        headers={"Authorization": f"Bearer {token1}"},
    )
    await client.post(
        "/api/v1/jobs",
        json=job_payload(title="Employer 2 Job"),
        headers={"Authorization": f"Bearer {token2}"},
    )

    response = await client.get(
        "/api/v1/jobs/mine",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert response.status_code == 200
    titles = [j["title"] for j in response.json()["items"]]
    assert "Employer 1 Job" in titles
    assert "Employer 2 Job" not in titles


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_list_returns_all_jobs(client, db_session):
    """GET /jobs/admin/jobs returns all jobs regardless of status."""
    from tests.conftest import make_employer, make_job

    admin_token = await register_and_promote(client, db_session, "ADMIN")

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

    response = await client.get(
        "/api/v1/jobs/admin/jobs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    titles = [j["title"] for j in response.json()["items"]]
    assert "Active" in titles
    assert "Draft" in titles
    assert "Closed" in titles


@pytest.mark.asyncio
async def test_admin_endpoint_returns_403_for_employer(client, db_session):
    """GET /jobs/admin/jobs returns 403 for non-admin users."""
    token = await register_and_promote(client, db_session, "EMPLOYER")

    response = await client.get(
        "/api/v1/jobs/admin/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
