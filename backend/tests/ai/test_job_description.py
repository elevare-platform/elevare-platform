"""Tests for Phase 1 — AI Job Description Writer.

Covers:
- Prompt builder output contains mode-appropriate instructions
- MockAIService response shape
- Router auth: 401 (unauthenticated), 403 (non-employer)
- Router 200 happy path for GENERATE and IMPROVE modes
- Router 400 when IMPROVE is called without current_text
"""

import pytest

from app.modules.ai.enums import JobDescriptionField, JobDescriptionMode
from app.modules.ai.prompts.job_description import build_job_description_prompt
from app.modules.ai.schema import JobContext
from app.modules.ai.service import MockAIService
from tests.conftest import make_register_data


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_job_context(**overrides) -> JobContext:
    defaults = {
        "title": "Backend Engineer",
        "seniority": "Mid",
        "skills": ["Python", "FastAPI"],
        "industry": "Technology",
        "company_name": "Acme Ltd",
    }
    defaults.update(overrides)
    return JobContext(**defaults)


async def register_employer(client, db_session):
    from app.modules.auth.jwt_handler import create_token_pair
    from sqlalchemy import select

    from app.modules.users.models import EmployerProfile, User

    data = make_register_data(role="EMPLOYER")
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
    user.role = "EMPLOYER"
    user.account_status = "ACTIVE"
    await db_session.flush()

    profile = EmployerProfile(
        user_id=user.id,
        company_name="Acme Ltd",
        industry="Technology",
        company_size="11-50",
        is_profile_complete=True,
        kyc_status="APPROVED",
    )
    db_session.add(profile)
    await db_session.flush()

    token_pair = create_token_pair(user.id, "EMPLOYER")
    return token_pair["access_token"], user


async def register_candidate(client, db_session):
    from app.modules.auth.jwt_handler import create_token_pair
    from sqlalchemy import select

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
    user.account_status = "ACTIVE"
    await db_session.flush()

    token_pair = create_token_pair(user.id, "CANDIDATE")
    return token_pair["access_token"], user


# ---------------------------------------------------------------------------
# Unit tests — prompt builder
# ---------------------------------------------------------------------------

def test_prompt_builder_generate_mode_contains_field_label():
    """GENERATE prompt mentions the target field."""
    prompt = build_job_description_prompt(
        mode=JobDescriptionMode.GENERATE,
        field=JobDescriptionField.ABOUT_THE_ROLE,
        current_text=None,
        job_context=make_job_context(),
    )
    assert "about_the_role" in prompt
    assert "scratch" in prompt.lower()


def test_prompt_builder_improve_mode_includes_existing_text():
    """IMPROVE prompt embeds the existing text."""
    existing = "We are looking for a developer."
    prompt = build_job_description_prompt(
        mode=JobDescriptionMode.IMPROVE,
        field=JobDescriptionField.ABOUT_THE_ROLE,
        current_text=existing,
        job_context=make_job_context(),
    )
    assert existing in prompt
    assert "Improve" in prompt


def test_prompt_builder_generate_with_no_current_text_omits_existing_section():
    """GENERATE prompt has no 'Existing text' block when current_text is None."""
    prompt = build_job_description_prompt(
        mode=JobDescriptionMode.GENERATE,
        field=JobDescriptionField.KEY_RESPONSIBILITIES,
        current_text=None,
        job_context=make_job_context(),
    )
    assert "Existing text:" not in prompt


def test_prompt_builder_includes_job_context_fields():
    """Prompt embeds title, seniority, skills from job_context."""
    ctx = make_job_context(title="Data Engineer", seniority="Senior", skills=["Spark", "Kafka"])
    prompt = build_job_description_prompt(
        mode=JobDescriptionMode.GENERATE,
        field=JobDescriptionField.REQUIREMENTS,
        current_text=None,
        job_context=ctx,
    )
    assert "Data Engineer" in prompt
    assert "Senior" in prompt
    assert "Spark" in prompt
    assert "Kafka" in prompt


# ---------------------------------------------------------------------------
# Unit tests — MockAIService
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_service_returns_string():
    """MockAIService.generate_job_description_text returns a non-empty string."""
    service = MockAIService()
    result = await service.generate_job_description_text(
        mode=JobDescriptionMode.GENERATE.value,
        field=JobDescriptionField.ABOUT_THE_ROLE.value,
        current_text=None,
        job_context=make_job_context(),
    )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_mock_service_improve_mode_returns_string():
    """MockAIService handles IMPROVE mode with existing text."""
    service = MockAIService()
    result = await service.generate_job_description_text(
        mode=JobDescriptionMode.IMPROVE.value,
        field=JobDescriptionField.KEY_RESPONSIBILITIES.value,
        current_text="Lead backend services.",
        job_context=make_job_context(),
    )
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Integration tests — router auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_description_endpoint_401_unauthenticated(client):
    """POST /ai/job-description returns 401 with no token."""
    resp = await client.post(
        "/api/v1/ai/job-description",
        json={
            "mode": "GENERATE",
            "field": "about_the_role",
            "job_context": {"title": "Engineer"},
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_job_description_endpoint_403_for_candidate(client, db_session):
    """POST /ai/job-description returns 403 for a candidate user."""
    candidate_token, _ = await register_candidate(client, db_session)

    resp = await client.post(
        "/api/v1/ai/job-description",
        json={
            "mode": "GENERATE",
            "field": "about_the_role",
            "job_context": {"title": "Engineer"},
        },
        headers={"Authorization": f"Bearer {candidate_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Integration tests — happy path and validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_job_description_generate_returns_200(client, db_session):
    """GENERATE mode returns a 200 with generated_text, mode, and field."""
    from unittest.mock import patch

    from app.modules.ai.service import MockAIService

    employer_token, _ = await register_employer(client, db_session)

    with patch("app.modules.ai.router.get_ai_service", return_value=MockAIService()):
        resp = await client.post(
            "/api/v1/ai/job-description",
            json={
                "mode": "GENERATE",
                "field": "about_the_role",
                "job_context": {
                    "title": "Backend Engineer",
                    "seniority": "Mid",
                    "skills": ["Python", "FastAPI"],
                },
            },
            headers={"Authorization": f"Bearer {employer_token}"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "generated_text" in body
    assert body["mode"] == "GENERATE"
    assert body["field"] == "about_the_role"
    assert len(body["generated_text"]) > 0


@pytest.mark.asyncio
async def test_job_description_improve_returns_200(client, db_session):
    """IMPROVE mode with current_text returns 200."""
    from unittest.mock import patch

    from app.modules.ai.service import MockAIService

    employer_token, _ = await register_employer(client, db_session)

    with patch("app.modules.ai.router.get_ai_service", return_value=MockAIService()):
        resp = await client.post(
            "/api/v1/ai/job-description",
            json={
                "mode": "IMPROVE",
                "field": "key_responsibilities",
                "current_text": "Lead backend development and mentor junior developers.",
                "job_context": {"title": "Senior Engineer"},
            },
            headers={"Authorization": f"Bearer {employer_token}"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "IMPROVE"
    assert body["field"] == "key_responsibilities"


@pytest.mark.asyncio
async def test_job_description_improve_without_text_returns_400(client, db_session):
    """IMPROVE mode without current_text returns 400."""
    from unittest.mock import patch

    from app.modules.ai.service import MockAIService

    employer_token, _ = await register_employer(client, db_session)

    with patch("app.modules.ai.router.get_ai_service", return_value=MockAIService()):
        resp = await client.post(
            "/api/v1/ai/job-description",
            json={
                "mode": "IMPROVE",
                "field": "about_the_role",
                "job_context": {"title": "Engineer"},
            },
            headers={"Authorization": f"Bearer {employer_token}"},
        )

    assert resp.status_code == 400
    assert "current_text" in resp.json()["message"].lower()
