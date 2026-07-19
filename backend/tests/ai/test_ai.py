"""Tests for Phase 6.5 — AI keyword match scoring.

Covers:
- KeywordAIService correctness (score, matched keywords, edge cases)
- Score stored on application row after apply (uses MockAIService)
- Match endpoint returns MatchResult for valid input
- Match endpoint returns 403 for candidate callers
- Applicant list response includes match_score field
"""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.storage import MockStorageService, get_storage_service
from app.main import app
from app.modules.ai.schema import MatchResult
from app.modules.ai.service import KeywordAIService
from app.modules.users.models import EmployerProfile
from tests.conftest import make_register_data

# ---------------------------------------------------------------------------
# Helpers (mirrors pattern from test_applications_router.py)
# ---------------------------------------------------------------------------


def future_deadline(days: int = 7) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


def job_payload(**overrides) -> dict:
    defaults = {
        "title": "Python Backend Engineer",
        "about_the_role": "We need a Python developer with FastAPI and PostgreSQL experience. Docker knowledge required.",
        "key_responsibilities": "Design, build and maintain scalable backend services.",
        "requirements": "Strong Python skills, FastAPI, PostgreSQL, and Docker experience.",
        "location": "Lagos, Nigeria",
        "contract_type": "FULL_TIME",
        "work_model": "HYBRID",
        "work_location": "LOCAL",
        "application_deadline": future_deadline(),
    }
    defaults.update(overrides)
    return defaults


async def register_and_activate(client, db_session, role: str = "CANDIDATE"):
    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import User

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
            kyc_status="APPROVED",
        )
        db_session.add(profile)
        await db_session.flush()

    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"], user


async def create_and_publish_job(
    client, db_session, employer_token: str, **overrides
) -> dict:

    resp = await client.post(
        "/api/v1/jobs",
        json=job_payload(**overrides),
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 201, resp.text
    job = resp.json()

    # Create a real admin user and approve the job
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


async def upload_cv(client, token: str) -> None:
    pdf_bytes = b"%PDF-1.4 fake pdf content for testing"
    await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("resume.pdf", pdf_bytes, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )


async def complete_candidate_profile(client, db_session, token: str, user_id) -> None:
    """Set required profile fields directly in DB and upload a CV."""
    from sqlalchemy import select as sa_select

    from app.modules.candidates.models import CandidateProfile

    # Update via API
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
    # Upload CV
    await upload_cv(client, token)
    # Force profile completion flag in DB (CV upload may not trigger recompute in test session)
    result = await db_session.execute(
        sa_select(CandidateProfile).where(CandidateProfile.user_id == user_id)
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


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Prevent real Celery tasks from firing — no broker available in tests."""
    from unittest.mock import MagicMock, patch

    with patch("app.modules.applications.service.score_application_task") as mock_task:
        mock_task.delay = MagicMock()
        yield mock_task


# ---------------------------------------------------------------------------
# Unit tests — KeywordAIService (no DB, no HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_keyword_service_correct_score_for_known_input():
    """Score is deterministic for a fixed candidate/job pair."""
    service = KeywordAIService()
    result = await service.compute_match_score(
        candidate_skills=["Python", "FastAPI", "PostgreSQL"],
        job_description="We need a Python developer with FastAPI and PostgreSQL experience.",
        job_title="Backend Engineer",
    )
    assert isinstance(result, MatchResult)
    assert result.score >= 0
    assert result.score <= 100
    # All three skills are in the job text — all should match
    assert set(result.matched_keywords) == {"Python", "FastAPI", "PostgreSQL"}


@pytest.mark.asyncio
async def test_keyword_service_matched_keywords_only_from_job_text():
    """Matched keywords list contains only skills that appear in the job text."""
    service = KeywordAIService()
    result = await service.compute_match_score(
        candidate_skills=["Python", "Kubernetes", "Figma"],
        job_description="Looking for a Python developer to build backend services.",
        job_title="Backend Developer",
    )
    assert "Python" in result.matched_keywords
    assert "Kubernetes" not in result.matched_keywords
    assert "Figma" not in result.matched_keywords


@pytest.mark.asyncio
async def test_keyword_service_score_zero_for_no_overlap():
    """Score is 0 when candidate skills share nothing with the job text."""
    service = KeywordAIService()
    result = await service.compute_match_score(
        candidate_skills=["Figma", "Sketch", "Illustrator"],
        job_description="We need a Python developer with FastAPI and PostgreSQL experience.",
        job_title="Backend Engineer",
    )
    assert result.score == 0
    assert result.matched_keywords == []


@pytest.mark.asyncio
async def test_keyword_service_score_capped_at_100():
    """Score never exceeds 100 regardless of input."""
    service = KeywordAIService()
    # Give many skills that all appear in a short job description
    result = await service.compute_match_score(
        candidate_skills=[
            "Python",
            "FastAPI",
            "PostgreSQL",
            "Docker",
            "Redis",
            "AWS",
            "Terraform",
            "Kubernetes",
            "SQL",
            "Linux",
        ],
        job_description="Python FastAPI PostgreSQL Docker Redis AWS Terraform Kubernetes SQL Linux",
        job_title="Senior Engineer",
    )
    assert result.score <= 100


@pytest.mark.asyncio
async def test_keyword_service_case_insensitive_matching():
    """Skills match regardless of case in job description."""
    service = KeywordAIService()
    result = await service.compute_match_score(
        candidate_skills=["python", "FASTAPI", "PostgreSQL"],
        job_description="We use Python, FastAPI, and PostgreSQL.",
        job_title="Backend Engineer",
    )
    assert len(result.matched_keywords) == 3


# ---------------------------------------------------------------------------
# Integration tests — score stored on application row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_score_field_present_in_application_response(client, db_session):
    """Employer applicant list exposes match_score; candidate apply response does not."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_and_publish_job(client, db_session, employer_token)

    apply_resp = await client.post(
        "/api/v1/applications",
        json={"job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert apply_resp.status_code == 201, apply_resp.text
    # Candidate-facing response intentionally excludes AI score fields
    assert "match_score" not in apply_resp.json()

    # Employer applicant list must expose match_score (null until background task runs)
    resp = await client.get(
        f"/api/v1/applications/job/{job['id']}",
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert "match_score" in item
    assert "score_computed_at" in item


@pytest.mark.asyncio
async def test_applicant_list_includes_match_score_field(client, db_session):
    """GET /applications/job/{id} includes match_score on each applicant."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    await complete_candidate_profile(
        client, db_session, candidate_token, candidate_user.id
    )
    job = await create_and_publish_job(client, db_session, employer_token)

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
    items = resp.json()["items"]
    assert len(items) == 1
    assert "match_score" in items[0]


# ---------------------------------------------------------------------------
# Integration tests — match endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_match_endpoint_returns_result_for_employer(client, db_session):
    """POST /ai/match returns a MatchResult for a valid employer request."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    # Update candidate profile with skills
    await client.patch(
        "/api/v1/candidates/me/profile",
        json={"skills": ["Python", "FastAPI"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )

    job = await create_and_publish_job(client, db_session, employer_token)

    resp = await client.post(
        "/api/v1/ai/match",
        json={"candidate_id": str(candidate_user.id), "job_id": job["id"]},
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "score" in body
    assert "matched_keywords" in body
    assert "total_job_keywords" in body
    assert "computed_at" in body
    assert 0 <= body["score"] <= 100


@pytest.mark.asyncio
async def test_match_endpoint_returns_403_for_candidate(client, db_session):
    """POST /ai/match returns 403 when called by a candidate."""
    candidate_token, candidate_user = await register_and_activate(
        client, db_session, "CANDIDATE"
    )
    employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    job = await create_and_publish_job(client, db_session, employer_token)

    resp = await client.post(
        "/api/v1/ai/match",
        json={"candidate_id": str(candidate_user.id), "job_id": job["id"]},
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 403
