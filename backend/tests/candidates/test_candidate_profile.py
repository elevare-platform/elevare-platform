"""Tests for candidate profile, CV, and document endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import MockStorageService, get_storage_service
from app.main import app
from app.modules.candidates.models import (
    CandidateCvs,
    CandidateDocuments,
    CandidateProfile,
)
from app.modules.users.models import User
from tests.conftest import make_register_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_pdf_bytes() -> bytes:
    """Minimal valid PDF magic bytes — passes magic bytes check."""
    return b"%PDF-1.4 fake pdf content for testing purposes"


def make_png_bytes() -> bytes:
    """Minimal PNG magic bytes."""
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


async def register_candidate(client: AsyncClient) -> tuple[str, str]:
    """Register a candidate and return (access_token, email)."""
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
    return resp.json()["access_token"], data.email


async def get_active_token(
    client: AsyncClient, db_session: AsyncSession, role: str = "CANDIDATE"
) -> str:
    """Register a user, activate them, return a token."""
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

    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"]


# ---------------------------------------------------------------------------
# Fixture: override storage with MockStorageService for all tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def override_storage():
    """Force MockStorageService for every test — no real R2 calls."""
    app.dependency_overrides[get_storage_service] = lambda: MockStorageService()
    yield
    # client fixture clears all overrides, but be explicit here too
    app.dependency_overrides.pop(get_storage_service, None)


# ---------------------------------------------------------------------------
# Task 1 — Registration creates skeleton CandidateProfile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_registration_creates_candidate_profile(client, db_session):
    """Registering as CANDIDATE atomically creates a CandidateProfile row."""
    _, email = await register_candidate(client)

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()

    profile_result = await db_session.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()

    assert profile is not None
    assert profile.user_id == user.id
    assert profile.is_profile_complete is False


# ---------------------------------------------------------------------------
# Profile update & completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_update_sets_fields(client, db_session):
    """PUT /candidates/me updates profile fields."""
    token = await get_active_token(client, db_session)

    resp = await client.put(
        "/api/v1/candidates/me",
        json={"bio": "I am a developer", "location": "Lagos"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["bio"] == "I am a developer"
    assert resp.json()["location"] == "Lagos"


@pytest.mark.asyncio
async def test_profile_incomplete_when_missing_fields(client, db_session):
    """is_profile_complete stays False when required fields are missing."""
    token = await get_active_token(client, db_session)

    resp = await client.put(
        "/api/v1/candidates/me",
        json={"bio": "Only bio set"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_profile_complete"] is False


@pytest.mark.asyncio
async def test_profile_complete_when_all_required_fields_set(client, db_session):
    """is_profile_complete flips to True when all four required fields and a CV are set."""
    token = await get_active_token(client, db_session)

    # Upload a CV — required for profile completion
    await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.put(
        "/api/v1/candidates/me",
        json={
            "bio": "Experienced developer",
            "skills": ["Python", "FastAPI"],
            "years_of_experience": 3,
            "location": "Lagos, Nigeria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_profile_complete"] is True


@pytest.mark.asyncio
async def test_profile_update_is_partial(client, db_session):
    """PUT /candidates/me does not overwrite fields not included in the request."""
    token = await get_active_token(client, db_session)

    await client.put(
        "/api/v1/candidates/me",
        json={"bio": "First bio", "location": "Abuja"},
        headers={"Authorization": f"Bearer {token}"},
    )

    resp = await client.put(
        "/api/v1/candidates/me",
        json={"skills": ["Python"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    # bio and location should still be set from the first update
    assert resp.json()["bio"] == "First bio"
    assert resp.json()["location"] == "Abuja"


# ---------------------------------------------------------------------------
# CV upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cv_upload_succeeds(client, db_session):
    """POST /candidates/me/cv stores cv_key and returns CV response."""
    token = await get_active_token(client, db_session)

    resp = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("resume.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["filename"] == "resume.pdf"
    assert "key" in body
    assert body["is_default"] is True  # first CV is always default


@pytest.mark.asyncio
async def test_second_cv_not_default(client, db_session):
    """Second CV upload is not set as default automatically."""
    token = await get_active_token(client, db_session)

    await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("first.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("second.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["is_default"] is False


@pytest.mark.asyncio
async def test_cv_upload_rejects_non_pdf_extension(client, db_session):
    """POST /candidates/me/cv rejects files with non-PDF extension."""
    token = await get_active_token(client, db_session)

    resp = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("resume.docx", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_FILE_TYPE"


@pytest.mark.asyncio
async def test_cv_upload_rejects_wrong_magic_bytes(client, db_session):
    """POST /candidates/me/cv rejects a file renamed to .pdf with wrong content."""
    token = await get_active_token(client, db_session)

    resp = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("resume.pdf", b"This is not a PDF at all", "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "INVALID_FILE_CONTENT"


@pytest.mark.asyncio
async def test_cv_upload_rejects_oversized_file(client, db_session):
    """POST /candidates/me/cv rejects files over 5MB."""
    token = await get_active_token(client, db_session)

    big_file = b"%PDF-1.4 " + b"x" * (5 * 1024 * 1024 + 1)

    resp = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("big.pdf", big_file, "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 413
    assert resp.json()["code"] == "FILE_TOO_LARGE"


# ---------------------------------------------------------------------------
# CV default & delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_cv_default(client, db_session):
    """PUT /candidates/me/cv/{id}/default sets the chosen CV as default."""
    token = await get_active_token(client, db_session)

    await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("first.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    second = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("second.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    second_id = second.json()["id"]

    resp = await client.put(
        f"/api/v1/candidates/me/cv/{second_id}/default",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Verify in DB
    result = await db_session.execute(
        select(CandidateCvs).where(CandidateCvs.id == second_id)
    )
    cv = result.scalar_one()
    assert cv.is_default is True


@pytest.mark.asyncio
async def test_delete_default_cv_promotes_next(client, db_session):
    """Deleting the default CV promotes the next most recent CV to default."""
    token = await get_active_token(client, db_session)

    first = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("first.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    second = await client.post(
        "/api/v1/candidates/me/cv",
        files={"file": ("second.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    first_id = first.json()["id"]
    second_id = second.json()["id"]

    # first is default — delete it
    resp = await client.delete(
        f"/api/v1/candidates/me/cv/{first_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(CandidateCvs).where(CandidateCvs.id == second_id)
    )
    cv = result.scalar_one()
    assert cv.is_default is True


# ---------------------------------------------------------------------------
# Document upload & delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_document_upload_succeeds(client, db_session):
    """POST /candidates/me/documents stores document and returns response."""
    token = await get_active_token(client, db_session)

    resp = await client.post(
        "/api/v1/candidates/me/documents",
        files={"file": ("certificate.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["filename"] == "certificate.pdf"
    assert resp.json()["document_type"] == "pdf"


@pytest.mark.asyncio
async def test_document_delete_removes_from_db(client, db_session):
    """DELETE /candidates/me/documents/{id} removes the document row."""
    token = await get_active_token(client, db_session)

    upload = await client.post(
        "/api/v1/candidates/me/documents",
        files={"file": ("cert.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    doc_id = upload.json()["id"]

    resp = await client.delete(
        f"/api/v1/candidates/me/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    result = await db_session.execute(
        select(CandidateDocuments).where(CandidateDocuments.id == doc_id)
    )
    assert result.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_employer_cannot_access_own_profile_endpoint(client, db_session):
    """GET /candidates/me returns 403 for employers."""
    token = await get_active_token(client, db_session, role="EMPLOYER")

    resp = await client.get(
        "/api/v1/candidates/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(client):
    """GET /candidates/me without token returns 401."""
    resp = await client.get("/api/v1/candidates/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_list_all_candidates(client, db_session):
    """GET /candidates returns 200 for admin."""
    token = await get_active_token(client, db_session, role="ADMIN")

    resp = await client.get(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_candidate_cannot_list_all_candidates(client, db_session):
    """GET /candidates returns 403 for candidates."""
    token = await get_active_token(client, db_session, role="CANDIDATE")

    resp = await client.get(
        "/api/v1/candidates",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
