"""Tests for POST /contact and GET /sitemap.xml and GET /robots.txt endpoints."""

import pytest

from app.modules.jobs.enums import JobStatus, ModerationStatus


# ─── Contact endpoint ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_contact_valid_submission_returns_200(client, db_session):
    """Valid contact submission is stored in DB and returns 200."""
    from sqlalchemy import select
    from app.modules.contact.models import ContactSubmission

    payload = {
        "name": "Test User",
        "email": "test_valid_unique_abc123@example.com",
        "message": "This is a test message that is long enough to pass validation.",
        "inquiry_type": "general",
        "honeypot": "",
    }

    response = await client.post("/api/v1/contact", json=payload)

    assert response.status_code == 200
    assert "thank you" in response.json()["message"].lower()

    result = await db_session.execute(
        select(ContactSubmission).where(ContactSubmission.email == "test_valid_unique_abc123@example.com")
    )
    submission = result.scalar_one_or_none()
    assert submission is not None
    assert submission.inquiry_type == "general"


@pytest.mark.asyncio
async def test_contact_honeypot_returns_200_without_db_record(client, db_session):
    """Honeypot-filled submission returns 200 silently but creates no DB record."""
    from sqlalchemy import select
    from app.modules.contact.models import ContactSubmission

    unique_email = "bot_12345_unique@spam.com"
    payload = {
        "name": "Bot",
        "email": unique_email,
        "message": "Buy cheap stuff now click here for amazing deals today!",
        "inquiry_type": "general",
        "honeypot": "filled by bot",
    }

    response = await client.post("/api/v1/contact", json=payload)

    assert response.status_code == 200

    result = await db_session.execute(
        select(ContactSubmission).where(ContactSubmission.email == unique_email)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_contact_invalid_email_returns_422(client):
    """Invalid email address returns a 422 validation error."""
    payload = {
        "name": "Test User",
        "email": "not-an-email",
        "message": "This is a test message that is long enough to pass.",
        "inquiry_type": "general",
    }

    response = await client.post("/api/v1/contact", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_contact_short_message_returns_422(client):
    """Message shorter than 20 characters returns a 422 validation error."""
    payload = {
        "name": "Test User",
        "email": "test@example.com",
        "message": "Too short",
        "inquiry_type": "general",
    }

    response = await client.post("/api/v1/contact", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_contact_employer_inquiry_routes_correctly(client, db_session):
    """Employer inquiry is stored with correct inquiry_type."""
    from sqlalchemy import select
    from app.modules.contact.models import ContactSubmission

    unique_email = "employer_test_unique@company.com"
    payload = {
        "name": "Employer User",
        "email": unique_email,
        "company": "Acme Corp",
        "message": "We are looking to hire several engineers for our team this quarter.",
        "inquiry_type": "employer_inquiry",
    }

    response = await client.post("/api/v1/contact", json=payload)

    assert response.status_code == 200

    result = await db_session.execute(
        select(ContactSubmission).where(ContactSubmission.email == unique_email)
    )
    submission = result.scalar_one_or_none()
    assert submission is not None
    assert submission.inquiry_type == "employer_inquiry"


# ─── Sitemap endpoint ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sitemap_returns_valid_xml(client):
    """GET /sitemap.xml returns 200 with application/xml content type."""
    response = await client.get("/sitemap.xml")

    assert response.status_code == 200
    assert "application/xml" in response.headers["content-type"]
    assert '<?xml version="1.0"' in response.text
    assert "<urlset" in response.text


@pytest.mark.asyncio
async def test_sitemap_includes_active_approved_jobs(client, db_session):
    """Sitemap includes URLs for ACTIVE + APPROVED jobs."""
    from tests.conftest import make_employer, make_job

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    active_job = make_job(
        employer.id,
        status=JobStatus.ACTIVE.value,
        moderation_status=ModerationStatus.APPROVED.value,
    )
    db_session.add(active_job)
    await db_session.flush()

    # Clear sitemap cache so the test job is included
    from app.core.dependencies import get_redis_client
    async for redis in get_redis_client():
        await redis.delete("sitemap:xml")

    response = await client.get("/sitemap.xml")

    assert str(active_job.id) in response.text


@pytest.mark.asyncio
async def test_sitemap_excludes_draft_and_pending_jobs(client, db_session):
    """Sitemap excludes jobs that are DRAFT or PENDING moderation."""
    from tests.conftest import make_employer, make_job
    from app.core.dependencies import get_redis_client

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    draft_job = make_job(
        employer.id,
        status=JobStatus.DRAFT.value,
        moderation_status=ModerationStatus.PENDING.value,
    )
    db_session.add(draft_job)
    await db_session.flush()

    async for redis in get_redis_client():
        await redis.delete("sitemap:xml")

    response = await client.get("/sitemap.xml")

    assert str(draft_job.id) not in response.text


# ─── Robots.txt endpoint ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_robots_txt_returns_correct_disallow_rules(client):
    """GET /robots.txt disallows authenticated and API routes."""
    response = await client.get("/robots.txt")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]

    body = response.text
    assert "Disallow: /admin" in body
    assert "Disallow: /candidate" in body
    assert "Disallow: /employer" in body
    assert "Disallow: /api" in body
    assert "Allow: /jobs" in body
    assert "Sitemap:" in body
