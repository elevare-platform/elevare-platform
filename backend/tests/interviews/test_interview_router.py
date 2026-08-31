"""HTTP-level tests for the interviews router — auth boundaries and the
public token endpoints' no-login access."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.conftest import make_employer, make_job

from .conftest import (
    make_application,
    make_interview,
    make_interview_list_entry,
    make_talent_pool_profile,
)


async def register_and_promote(client, db_session, role: str):
    """Register a user, promote them to `role`, and return (access_token, user).

    Mirrors tests/jobs/test_jobs_router.py's helper, extended to also create
    a CandidateProfile for CANDIDATE — the interviews router's `get_candidate`
    dependency needs one to resolve `candidate.user_id`.
    """
    from sqlalchemy import select

    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.candidates.models import CandidateProfile
    from app.modules.users.models import User
    from tests.conftest import make_organization_for, make_register_data

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
    user.role = role
    user.account_status = "ACTIVE"
    await db_session.flush()

    if role == "EMPLOYER":
        await make_organization_for(
            db_session,
            user,
            company_name="Test Corp",
            industry="Technology",
            company_size="11-50",
            is_profile_complete=True,
            kyc_status="APPROVED",
        )
    elif role == "CANDIDATE":
        existing = await db_session.execute(
            select(CandidateProfile).where(CandidateProfile.user_id == user.id)
        )
        if existing.scalar_one_or_none() is None:
            db_session.add(CandidateProfile(user_id=user.id))
            await db_session.flush()

    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"], user


# ---------------------------------------------------------------------------
# Candidate-scoped endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_candidate_cannot_access_another_candidates_application(
    client, db_session
):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    _owner_token, owner_user = await register_and_promote(client, db_session, "CANDIDATE")
    intruder_token, _intruder_user = await register_and_promote(
        client, db_session, "CANDIDATE"
    )

    application = await make_application(db_session, owner_user.id, job.id)

    resp = await client.get(
        f"/api/v1/interviews/applications/{application.id}",
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Employer-scoped endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_employer_cannot_send_invite_for_job_they_do_not_own(client, db_session):
    _owner_token, owner_user = await register_and_promote(client, db_session, "EMPLOYER")
    intruder_token, _intruder_user = await register_and_promote(
        client, db_session, "EMPLOYER"
    )

    job = make_job(owner_user.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    resp = await client.post(
        f"/api/v1/interviews/{uuid4()}/send-invite",
        params={"job_id": str(job.id)},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_employer_cannot_send_invites_to_all_for_job_they_do_not_own(
    client, db_session
):
    _owner_token, owner_user = await register_and_promote(client, db_session, "EMPLOYER")
    intruder_token, _intruder_user = await register_and_promote(
        client, db_session, "EMPLOYER"
    )

    job = make_job(owner_user.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    resp = await client.post(
        "/api/v1/interviews/send-invites",
        params={"job_id": str(job.id)},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_employer_cannot_view_interview_detail_for_job_they_do_not_own(
    client, db_session
):
    _owner_token, owner_user = await register_and_promote(client, db_session, "EMPLOYER")
    intruder_token, _intruder_user = await register_and_promote(
        client, db_session, "EMPLOYER"
    )

    job = make_job(owner_user.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()

    resp = await client.get(
        "/api/v1/interviews/detail",
        params={"job_id": str(job.id), "talent_pool_profile_id": str(uuid4())},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Public token routes — no Authorization header at all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_token_endpoint_works_with_no_authorization_header(
    client, db_session
):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview_list_entry(db_session, employer.id, tp_profile.id, job.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        token="public-test-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    await db_session.commit()

    resp = await client.get(f"/api/v1/public/interviews/{interview.token}")

    assert resp.status_code == 200
    assert resp.json()["job_title"] == job.title


@pytest.mark.asyncio
async def test_public_info_endpoint_is_rate_limited(client, db_session):
    """The public token routes have no login barrier at all, so they need
    their own rate limit — proves @limiter.limit is actually wired on the
    public_router, not just present on the (login-gated) auth routes."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    await make_interview_list_entry(db_session, employer.id, tp_profile.id, job.id)
    interview = await make_interview(
        db_session,
        job.id,
        tp_profile.id,
        token="rate-limit-test-token",
        token_expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    await db_session.commit()

    url = f"/api/v1/public/interviews/{interview.token}"
    for _ in range(30):
        resp = await client.get(url)
        assert resp.status_code == 200

    resp = await client.get(url)
    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_public_token_endpoint_rejects_unknown_token_with_no_auth(client):
    resp = await client.get("/api/v1/public/interviews/does-not-exist")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Admin cost summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_costs_endpoint_requires_admin(client, db_session):
    employer_token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    resp = await client.get(
        "/api/v1/interviews/costs",
        headers={"Authorization": f"Bearer {employer_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_costs_endpoint_breaks_down_by_component_current_month_only(
    client, db_session
):
    """Uses before/after deltas rather than absolute totals — this suite runs
    against a real shared dev database (not a throwaway test DB), so other
    genuine activity this month is expected and must not make the test flaky."""
    from app.modules.interviews.models import InterviewCost

    admin_token, _ = await register_and_promote(client, db_session, "ADMIN")

    baseline_resp = await client.get(
        "/api/v1/interviews/costs", headers={"Authorization": f"Bearer {admin_token}"}
    )
    baseline = baseline_resp.json()["by_component"]
    baseline_realtime_calls = baseline.get("realtime", {}).get("total_calls", 0)
    baseline_scoring_calls = baseline.get("scoring", {}).get("total_calls", 0)

    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief="Ask about distributed systems.")
    db_session.add(job)
    await db_session.flush()
    tp_profile = await make_talent_pool_profile(db_session, added_by_id=employer.id)
    interview = await make_interview(db_session, job.id, tp_profile.id)
    await db_session.flush()

    db_session.add_all(
        [
            InterviewCost(
                interview_id=interview.id,
                component="realtime",
                model="gpt-realtime",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=3.00,
            ),
            InterviewCost(
                interview_id=interview.id,
                component="scoring",
                model="claude-3-5-sonnet-20241022",
                input_tokens=1500,
                output_tokens=400,
                cost_usd=0.02,
            ),
            # Last month — must not appear in the current-month summary.
            InterviewCost(
                interview_id=interview.id,
                component="realtime",
                model="gpt-realtime",
                input_tokens=1000,
                output_tokens=500,
                cost_usd=3.00,
                created_at=datetime.now(UTC) - timedelta(days=45),
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/interviews/costs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["by_component"]["realtime"]["total_calls"] == baseline_realtime_calls + 1
    assert data["by_component"]["scoring"]["total_calls"] == baseline_scoring_calls + 1
    assert "transcription" not in data["by_component"]
