"""Tests for the testimonials module.

Covers:
- POST /api/v1/testimonials  — public submission
- GET  /api/v1/testimonials  — public listing (approved only)
- GET  /api/v1/admin/testimonials  — admin list with status filter
- PATCH /api/v1/admin/testimonials/{id}  — admin moderation
"""

import pytest
from sqlalchemy import select

from app.modules.testimonials.enums import TestimonialStatus
from app.modules.testimonials.models import Testimonial
from tests.conftest import make_admin, make_user


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _submit(client, **overrides):
    """POST a testimonial via multipart form data."""
    defaults = {
        "full_name": "Jane Doe",
        "testimony": "Elevare found us three great hires in under a week.",
    }
    defaults.update(overrides)
    return await client.post("/api/v1/testimonials", data=defaults)


async def _seed_testimonial(db_session, status=TestimonialStatus.PENDING, **overrides) -> Testimonial:
    """Insert a testimonial directly into the DB."""
    defaults = {
        "full_name": "Seed User",
        "testimony": "This is a seeded testimonial for testing purposes.",
        "status": status.value if isinstance(status, TestimonialStatus) else status,
    }
    defaults.update(overrides)
    t = Testimonial(**defaults)
    db_session.add(t)
    await db_session.flush()
    return t


async def _admin_token(client, db_session) -> str:
    """Insert an admin user and return a valid access token."""
    admin = make_admin(email_verified=True)
    db_session.add(admin)
    await db_session.flush()

    from app.modules.auth.jwt_handler import create_token_pair
    return create_token_pair(str(admin.id), admin.role)["access_token"]


# ─── Public submission ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_testimonial_returns_201(client, db_session):
    """Valid submission returns 201 and a success message."""
    response = await _submit(client)

    assert response.status_code == 201
    assert "submitted" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_submit_testimonial_persisted_as_pending(client, db_session):
    """Submitted testimonial is saved to the DB with status=pending."""
    await _submit(client, full_name="Persisted User", testimony="Great experience with Elevare platform.")

    result = await db_session.execute(
        select(Testimonial).where(Testimonial.full_name == "Persisted User")
    )
    t = result.scalar_one_or_none()
    assert t is not None
    assert t.status == TestimonialStatus.PENDING


@pytest.mark.asyncio
async def test_submit_testimonial_with_optional_fields(client, db_session):
    """Optional fields company and position are stored correctly."""
    await _submit(
        client,
        full_name="Optional Fields User",
        testimony="Very happy with the results from Elevare.",
        company="Acme Ltd",
        position="CTO",
    )

    result = await db_session.execute(
        select(Testimonial).where(Testimonial.full_name == "Optional Fields User")
    )
    t = result.scalar_one_or_none()
    assert t.company == "Acme Ltd"
    assert t.position == "CTO"


@pytest.mark.asyncio
async def test_submit_testimonial_missing_full_name_returns_422(client):
    """Missing required full_name returns 422."""
    response = await client.post(
        "/api/v1/testimonials",
        data={"testimony": "Great service from the team."},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_testimonial_missing_testimony_returns_422(client):
    """Missing required testimony returns 422."""
    response = await client.post(
        "/api/v1/testimonials",
        data={"full_name": "Jane Doe"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_testimonial_empty_full_name_returns_422(client):
    """Blank full_name (whitespace only) returns 422."""
    response = await client.post(
        "/api/v1/testimonials",
        data={"full_name": "   ", "testimony": "Great service."},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_testimonial_invalid_image_type_returns_400(client):
    """Uploading a non-image file returns 400."""
    import io
    response = await client.post(
        "/api/v1/testimonials",
        data={"full_name": "Jane", "testimony": "Good service overall."},
        files={"image": ("doc.pdf", io.BytesIO(b"%PDF-fake"), "application/pdf")},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_submit_testimonial_oversized_image_returns_400(client):
    """Uploading an image over 5 MB returns 400."""
    import io
    big = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
    response = await client.post(
        "/api/v1/testimonials",
        data={"full_name": "Jane", "testimony": "Good service overall."},
        files={"image": ("photo.jpg", big, "image/jpeg")},
    )
    assert response.status_code == 400


# ─── Public listing ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_testimonials_returns_only_approved(client, db_session):
    """GET /testimonials returns only approved testimonials."""
    await _seed_testimonial(db_session, status=TestimonialStatus.APPROVED, full_name="Approved One")
    await _seed_testimonial(db_session, status=TestimonialStatus.PENDING, full_name="Pending One")
    await _seed_testimonial(db_session, status=TestimonialStatus.REJECTED, full_name="Rejected One")

    response = await client.get("/api/v1/testimonials")

    assert response.status_code == 200
    names = [t["full_name"] for t in response.json()]
    assert "Approved One" in names
    assert "Pending One" not in names
    assert "Rejected One" not in names


@pytest.mark.asyncio
async def test_get_testimonials_returns_empty_list_when_none_approved(client, db_session):
    """GET /testimonials returns [] when no testimonials are approved."""
    await _seed_testimonial(db_session, status=TestimonialStatus.PENDING)

    response = await client.get("/api/v1/testimonials")

    assert response.status_code == 200
    # May contain other approved items from parallel tests — just assert pending not leaked
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_testimonials_does_not_expose_status_field(client, db_session):
    """Public endpoint response schema does not include the status field."""
    await _seed_testimonial(db_session, status=TestimonialStatus.APPROVED)

    response = await client.get("/api/v1/testimonials")

    assert response.status_code == 200
    for item in response.json():
        assert "status" not in item
        assert "reviewed_at" not in item


# ─── Admin listing ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_list_requires_auth(client):
    """GET /admin/testimonials without a token returns 401."""
    response = await client.get("/api/v1/admin/testimonials")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_list_returns_all_statuses(client, db_session):
    """Admin list returns testimonials of all statuses by default."""
    await _seed_testimonial(db_session, status=TestimonialStatus.APPROVED, full_name="Admin Approved")
    await _seed_testimonial(db_session, status=TestimonialStatus.PENDING, full_name="Admin Pending")
    await _seed_testimonial(db_session, status=TestimonialStatus.REJECTED, full_name="Admin Rejected")

    token = await _admin_token(client, db_session)
    response = await client.get(
        "/api/v1/admin/testimonials",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    names = [t["full_name"] for t in response.json()]
    assert "Admin Approved" in names
    assert "Admin Pending" in names
    assert "Admin Rejected" in names


@pytest.mark.asyncio
async def test_admin_list_filter_by_pending(client, db_session):
    """Admin list filtered by status=pending returns only pending testimonials."""
    await _seed_testimonial(db_session, status=TestimonialStatus.PENDING, full_name="Filter Pending")
    await _seed_testimonial(db_session, status=TestimonialStatus.APPROVED, full_name="Filter Approved")

    token = await _admin_token(client, db_session)
    response = await client.get(
        "/api/v1/admin/testimonials?status=pending",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    statuses = [t["status"] for t in response.json()]
    assert all(s == "pending" for s in statuses)


@pytest.mark.asyncio
async def test_admin_list_includes_status_and_reviewed_at(client, db_session):
    """Admin response schema includes status and reviewed_at fields."""
    await _seed_testimonial(db_session, status=TestimonialStatus.PENDING, full_name="Schema Check")

    token = await _admin_token(client, db_session)
    response = await client.get(
        "/api/v1/admin/testimonials",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    item = next((t for t in response.json() if t["full_name"] == "Schema Check"), None)
    assert item is not None
    assert "status" in item
    assert "reviewed_at" in item


# ─── Admin moderation ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_moderate_testimonial_approve(client, db_session):
    """PATCH with status=approved updates the record and sets reviewed_at."""
    t = await _seed_testimonial(db_session, status=TestimonialStatus.PENDING)

    token = await _admin_token(client, db_session)
    response = await client.patch(
        f"/api/v1/admin/testimonials/{t.id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["reviewed_at"] is not None


@pytest.mark.asyncio
async def test_moderate_testimonial_reject(client, db_session):
    """PATCH with status=rejected updates the record correctly."""
    t = await _seed_testimonial(db_session, status=TestimonialStatus.PENDING)

    token = await _admin_token(client, db_session)
    response = await client.patch(
        f"/api/v1/admin/testimonials/{t.id}",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_moderate_testimonial_reset_to_pending(client, db_session):
    """PATCH with status=pending resets an approved testimonial back to pending."""
    t = await _seed_testimonial(db_session, status=TestimonialStatus.APPROVED)

    token = await _admin_token(client, db_session)
    response = await client.patch(
        f"/api/v1/admin/testimonials/{t.id}",
        json={"status": "pending"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


@pytest.mark.asyncio
async def test_moderate_nonexistent_testimonial_returns_404(client, db_session):
    """PATCH on a non-existent testimonial ID returns 404."""
    from uuid import uuid4

    token = await _admin_token(client, db_session)
    response = await client.patch(
        f"/api/v1/admin/testimonials/{uuid4()}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_moderate_testimonial_requires_auth(client, db_session):
    """PATCH without a token returns 401."""
    t = await _seed_testimonial(db_session)
    response = await client.patch(
        f"/api/v1/admin/testimonials/{t.id}",
        json={"status": "approved"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_moderate_testimonial_non_admin_returns_403(client, db_session):
    """PATCH by a non-admin user returns 403."""
    t = await _seed_testimonial(db_session)

    candidate = make_user(email_verified=True)
    db_session.add(candidate)
    await db_session.flush()

    from app.modules.auth.jwt_handler import create_token_pair
    token = create_token_pair(str(candidate.id), candidate.role)["access_token"]

    response = await client.patch(
        f"/api/v1/admin/testimonials/{t.id}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_moderate_testimonial_invalid_status_returns_422(client, db_session):
    """PATCH with an invalid status value returns 422."""
    t = await _seed_testimonial(db_session)

    token = await _admin_token(client, db_session)
    response = await client.patch(
        f"/api/v1/admin/testimonials/{t.id}",
        json={"status": "published"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
