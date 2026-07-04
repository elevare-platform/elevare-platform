"""Integration tests for CV parsing endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.storage import MockStorageService, get_storage_service
from app.main import app
from app.modules.ai.models import ParsedCVSubmission
from app.modules.ai.enums import CVParsingStatus
from tests.conftest import make_register_data


def make_pdf_bytes() -> bytes:
    return b"%PDF-1.4 fake cv content for testing the cv parsing pipeline integration tests"


async def get_token(client: AsyncClient, db_session: AsyncSession, role: str = "ADMIN") -> str:
    from sqlalchemy import select
    from app.modules.users.models import User
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

    return create_token_pair(user.id, role)["access_token"]


@pytest.fixture(autouse=True)
def override_storage():
    app.dependency_overrides[get_storage_service] = lambda: MockStorageService()
    yield
    app.dependency_overrides.pop(get_storage_service, None)


@pytest.fixture(autouse=True)
def mock_celery_task():
    """Prevent real Celery tasks from firing in tests."""
    with patch("app.modules.ai.cv_parsing_service.run_full_pipeline_task") as mock_task:
        mock_task.delay = MagicMock()
        yield mock_task


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis to avoid real connections."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.setex = AsyncMock()
    mock.aclose = AsyncMock()

    from app.core.dependencies import get_redis_client

    async def override():
        yield mock

    app.dependency_overrides[get_redis_client] = override
    yield mock
    app.dependency_overrides.pop(get_redis_client, None)


# ── Submit CV ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_cv_creates_submission(client, db_session):
    token = await get_token(client, db_session, "ADMIN")

    resp = await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    sub_id = resp.json()["id"]

    result = await db_session.execute(select(ParsedCVSubmission).where(ParsedCVSubmission.id == sub_id))
    submission = result.scalar_one_or_none()
    assert submission is not None
    assert submission.parse_status == CVParsingStatus.PENDING.value


@pytest.mark.asyncio
async def test_submit_cv_cache_hit_returns_completed(client, db_session, mock_redis):
    import json
    cached_data = {"full_name": "John Doe", "email": "john@example.com", "skills": []}
    # Re-register the override so the client fixture's mock_redis uses our cached response
    from app.core.dependencies import get_redis_client
    configured_mock = AsyncMock()
    configured_mock.get = AsyncMock(return_value=json.dumps(cached_data).encode())
    configured_mock.setex = AsyncMock()

    async def override_with_cache():
        yield configured_mock

    app.dependency_overrides[get_redis_client] = override_with_cache

    token = await get_token(client, db_session, "ADMIN")

    resp = await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["parse_status"] == CVParsingStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_submit_cv_cache_miss_fires_background_task(client, db_session, mock_celery_task):
    token = await get_token(client, db_session, "ADMIN")

    await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )

    mock_celery_task.delay.assert_called_once()


# ── Get submission ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_submission_returns_data(client, db_session):
    token = await get_token(client, db_session, "ADMIN")

    submit = await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    sub_id = submit.json()["id"]

    resp = await client.get(
        f"/api/v1/cv-parsing/submissions/{sub_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == sub_id


@pytest.mark.asyncio
async def test_employer_cannot_see_other_employer_submission(client, db_session):
    admin_token = await get_token(client, db_session, "ADMIN")
    employer_token = await get_token(client, db_session, "EMPLOYER")

    submit = await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    sub_id = submit.json()["id"]

    resp = await client.get(
        f"/api/v1/cv-parsing/submissions/{sub_id}",
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 403


# ── No duplicate LLM cost on cache hit ───────────────────────────────────────

@pytest.mark.asyncio
async def test_same_cv_twice_no_second_llm_call(client, db_session, mock_celery_task, mock_redis):
    import json
    from app.core.dependencies import get_redis_client

    token = await get_token(client, db_session, "ADMIN")

    # First submission — cache miss, fires Celery
    await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mock_celery_task.delay.call_count == 1

    # Simulate cache populated — re-register override with cached response
    cached_data = {"full_name": "Test", "skills": []}
    cache_mock = AsyncMock()
    cache_mock.get = AsyncMock(return_value=json.dumps(cached_data).encode())
    cache_mock.setex = AsyncMock()

    async def override_with_cache():
        yield cache_mock

    app.dependency_overrides[get_redis_client] = override_with_cache

    # Second submission — cache hit, no new Celery task
    await client.post(
        "/api/v1/cv-parsing/submit",
        files={"file": ("cv.pdf", make_pdf_bytes(), "application/pdf")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert mock_celery_task.delay.call_count == 1  # still 1, not 2
