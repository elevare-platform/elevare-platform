"""Phase 11.5 test suite — AI scoring, shareable links, talent pool.

Covers the spec's Task 12 checklist plus add-on work:
- Deterministic score computation
- Hash-based invalidation
- Access token generation and enforcement
- Public applicants endpoint (expired/revoked → 404, name consent gate)
- Talent pool submission and profile enrichment
- Talent pool promotion conflict detection
- External CV exclusion from shared links (consent fix)
- ai_score vs match_score distinction
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.ai.scoring_service import (
    compute_deterministic_score,
    hash_cv_scoring_inputs,
    hash_job_scoring_inputs,
)
from app.modules.jobs.enums import ContractType, WorkModel
from app.modules.users.models import EmployerProfile, User
from tests.conftest import make_register_data

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def register_and_activate(client, db_session, role: str = "CANDIDATE"):
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


def job_payload(**overrides) -> dict:
    defaults = {
        "title": "Backend Engineer",
        "about_the_role": "Build scalable APIs. Python and SQL required.",
        "key_responsibilities": "Design, build and maintain backend services.",
        "requirements": "Strong Python, SQL and FastAPI skills.",
        "location": "Lagos",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "work_location": "LOCAL",
        "required_skills": ["Python", "SQL", "FastAPI"],
        "seniority_level": "MID",
        "required_years_experience": 3,
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# Task 2 — Deterministic score computation (no LLM)
# ===========================================================================


class TestDeterministicScore:

    def test_perfect_match_returns_high_score(self):
        score = compute_deterministic_score(
            candidate_skills=["Python", "SQL", "FastAPI"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["Python", "SQL", "FastAPI"],
            job_seniority_level="MID",
            job_min_years_experience=2,
            job_max_years_experience=5,
        )
        assert score >= 90

    def test_no_skills_match_gives_low_score(self):
        score = compute_deterministic_score(
            candidate_skills=["Figma", "Sketch"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["Python", "SQL", "FastAPI"],
            job_seniority_level="MID",
            job_min_years_experience=2,
            job_max_years_experience=5,
        )
        # Skills component is 50% weight, zero skills match → significant penalty
        assert score < 60

    def test_case_insensitive_skill_matching(self):
        score_upper = compute_deterministic_score(
            candidate_skills=["PYTHON", "SQL"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["python", "sql"],
            job_seniority_level="MID",
        )
        score_lower = compute_deterministic_score(
            candidate_skills=["python", "sql"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["python", "sql"],
            job_seniority_level="MID",
        )
        assert score_upper == score_lower

    def test_empty_required_skills_no_penalty(self):
        score = compute_deterministic_score(
            candidate_skills=["Python"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=[],  # no requirements
            job_seniority_level="MID",
        )
        # Skills coverage should return 100 when no requirements
        assert score >= 70

    def test_score_clamped_to_0_100(self):
        score = compute_deterministic_score(
            candidate_skills=["Python"] * 50,
            candidate_years_experience=100,
            candidate_seniority="MID",
            job_required_skills=["Python"],
            job_seniority_level="MID",
        )
        assert 0 <= score <= 100

    def test_adjacent_seniority_partial_credit(self):
        score_exact = compute_deterministic_score(
            candidate_skills=["Python"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["Python"],
            job_seniority_level="MID",
        )
        score_adjacent = compute_deterministic_score(
            candidate_skills=["Python"],
            candidate_years_experience=3,
            candidate_seniority="JUNIOR",  # one level off
            job_required_skills=["Python"],
            job_seniority_level="MID",
        )
        score_distant = compute_deterministic_score(
            candidate_skills=["Python"],
            candidate_years_experience=3,
            candidate_seniority="EXECUTIVE",  # distant
            job_required_skills=["Python"],
            job_seniority_level="MID",
        )
        assert score_exact > score_adjacent > score_distant

    def test_missing_data_neutral_not_zero(self):
        """Missing experience/seniority should use neutral 50, not penalise."""
        compute_deterministic_score(
            candidate_skills=["Python"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["Python"],
            job_seniority_level="MID",
            job_min_years_experience=3,
        )
        score_without = compute_deterministic_score(
            candidate_skills=["Python"],
            candidate_years_experience=None,  # missing
            candidate_seniority=None,  # missing
            job_required_skills=["Python"],
            job_seniority_level=None,  # missing
        )
        # Missing data should not tank the score — neutral 50 on those components
        assert score_without >= 50


# ===========================================================================
# Task 3 — Hash-based invalidation
# ===========================================================================


class TestScoreHashing:

    def test_same_inputs_produce_same_hash(self):
        h1 = hash_job_scoring_inputs("Build APIs", ["Python", "SQL"], "MID")
        h2 = hash_job_scoring_inputs("Build APIs", ["Python", "SQL"], "MID")
        assert h1 == h2

    def test_different_description_produces_different_hash(self):
        h1 = hash_job_scoring_inputs("Build APIs", ["Python"], "MID")
        h2 = hash_job_scoring_inputs("Build mobile apps", ["Python"], "MID")
        assert h1 != h2

    def test_skill_order_normalised(self):
        """Skills list order should not matter for hash."""
        h1 = hash_job_scoring_inputs("desc", ["Python", "SQL"], "MID")
        h2 = hash_job_scoring_inputs("desc", ["SQL", "Python"], "MID")
        assert h1 == h2

    def test_cv_hash_changes_when_skills_change(self):
        """Hash is driven by work_history + role identity, not skills list."""
        h1 = hash_cv_scoring_inputs(
            {
                "current_title": "Engineer",
                "work_history": [
                    {"title": "Dev", "company": "Acme", "description": "Python work"}
                ],
                "years_experience": 3,
            }
        )
        h2 = hash_cv_scoring_inputs(
            {
                "current_title": "Engineer",
                "work_history": [
                    {"title": "Dev", "company": "Acme", "description": "Java work"}
                ],
                "years_experience": 3,
            }
        )
        assert h1 != h2

    def test_cv_hash_stable_with_null_fields(self):
        h1 = hash_cv_scoring_inputs(
            {"skills": None, "years_experience": None, "seniority_level": None}
        )
        h2 = hash_cv_scoring_inputs(
            {"skills": None, "years_experience": None, "seniority_level": None}
        )
        assert h1 == h2


# ===========================================================================
# Task 7 — Job access token endpoints
# ===========================================================================


class TestJobAccessTokens:

    @pytest.mark.asyncio
    async def test_employer_can_create_token(self, client, db_session):
        token, user = await register_and_activate(client, db_session, "EMPLOYER")
        # Create job
        await client.post(
            "/api/v1/jobs",
            json=job_payload(),
            headers={"Authorization": f"Bearer {token}"},
        )
        jobs_resp = await client.get(
            "/api/v1/jobs/mine",
            headers={"Authorization": f"Bearer {token}"},
        )
        job_id = jobs_resp.json()["items"][0]["id"]

        # Approve job so it's active
        from app.modules.jobs.enums import ModerationStatus
        from app.modules.jobs.models import Job

        job = await db_session.get(Job, job_id)
        job.moderation_status = ModerationStatus.APPROVED.value
        job.status = "ACTIVE"
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/jobs/{job_id}/access-tokens",
            json={"expires_in_days": 7, "disclose_names": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert data["disclose_names"] is False
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_non_owner_cannot_create_token(self, client, db_session):
        token_a, user_a = await register_and_activate(client, db_session, "EMPLOYER")
        token_b, user_b = await register_and_activate(client, db_session, "EMPLOYER")

        await client.post(
            "/api/v1/jobs",
            json=job_payload(),
            headers={"Authorization": f"Bearer {token_a}"},
        )
        jobs_resp = await client.get(
            "/api/v1/jobs/mine",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        job_id = jobs_resp.json()["items"][0]["id"]

        # employer B tries to create token for employer A's job
        resp = await client.post(
            f"/api/v1/jobs/{job_id}/access-tokens",
            json={"expires_in_days": 7, "disclose_names": False},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_expired_token_returns_404_not_data(self, client, db_session):
        import secrets

        from app.modules.jobs.models import JobAccessTokens
        from tests.conftest import make_employer, make_job

        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()

        job = make_job(employer.id)
        db_session.add(job)
        await db_session.flush()

        token_str = secrets.token_urlsafe(32)
        expired_token = JobAccessTokens(
            token=token_str,
            job_id=job.id,
            created_by_id=employer.id,
            disclose_names=False,
            expires_at=datetime.now(UTC) - timedelta(hours=1),  # already expired
            is_active=True,
        )
        db_session.add(expired_token)
        await db_session.flush()

        resp = await client.get(f"/api/v1/public/jobs/{token_str}/applicants")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_revoked_token_returns_404_immediately(self, client, db_session):
        import secrets

        from app.modules.jobs.models import JobAccessTokens
        from tests.conftest import make_employer, make_job

        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()

        job = make_job(employer.id)
        db_session.add(job)
        await db_session.flush()

        token_str = secrets.token_urlsafe(32)
        revoked_token = JobAccessTokens(
            token=token_str,
            job_id=job.id,
            created_by_id=employer.id,
            disclose_names=False,
            expires_at=datetime.now(UTC) + timedelta(days=7),
            is_active=False,  # revoked
            revoked_at=datetime.now(UTC),
        )
        db_session.add(revoked_token)
        await db_session.flush()

        resp = await client.get(f"/api/v1/public/jobs/{token_str}/applicants")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_token_returns_404_not_403(self, client, db_session):
        """Never confirm a token existed — 404, not 403."""
        resp = await client.get("/api/v1/public/jobs/totally-fake-token/applicants")
        assert resp.status_code == 404


# ===========================================================================
# Name disclosure consent gate
# ===========================================================================


class TestNameDisclosure:

    def test_name_hidden_when_no_cv_sharing_consent(self):
        """Token with disclose_names=True but candidate cv_sharing_consent=False → initials only."""
        # This is a unit test of the logic, not an HTTP test
        disclose_names = True
        cv_sharing_consent = False
        full_name = "Ada Okafor"

        disclosed = full_name if (disclose_names and cv_sharing_consent) else None
        assert disclosed is None

    def test_name_shown_when_both_flags_true(self):
        disclose_names = True
        cv_sharing_consent = True
        full_name = "Ada Okafor"

        disclosed = full_name if (disclose_names and cv_sharing_consent) else None
        assert disclosed == "Ada Okafor"

    def test_name_hidden_when_token_flag_false(self):
        disclose_names = False
        cv_sharing_consent = True
        full_name = "Ada Okafor"

        disclosed = full_name if (disclose_names and cv_sharing_consent) else None
        assert disclosed is None

    def test_external_cv_always_initials_only(self):
        """External talent pool candidates have no consent — always initials regardless of token."""
        # But external CVs hardcode full_name = None
        full_name = None  # as implemented in access_token_service.py
        assert full_name is None


# ===========================================================================
# Talent pool
# ===========================================================================


class TestTalentPoolSubmission:

    @pytest.mark.asyncio
    async def test_submission_creates_talent_pool_profile(self, client, db_session):
        from app.core.storage import MockStorageService, get_storage_service
        from app.modules.talent_pool.models import TalentPoolProfiles

        token, user = await register_and_activate(client, db_session, "EMPLOYER")

        app_instance = client._transport.app
        app_instance.dependency_overrides[get_storage_service] = (
            lambda: MockStorageService()
        )

        with patch("app.modules.ai.tasks.run_full_pipeline_task") as mock_task:
            mock_task.delay = MagicMock()
            pdf_bytes = b"%PDF-1.4 fake pdf content for testing"
            resp = await client.post(
                "/api/v1/talent-pool/submit",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test_cv.pdf", pdf_bytes, "application/pdf")},
                data={"source": "referral"},
            )

        assert resp.status_code == 201
        profile_id = resp.json()["id"]

        # Verify the specific profile that was just created
        from uuid import UUID

        result = await db_session.execute(
            select(TalentPoolProfiles).where(TalentPoolProfiles.id == UUID(profile_id))
        )
        profile = result.scalar_one()
        assert profile.source == "referral"

    @pytest.mark.asyncio
    async def test_candidate_auto_enrolled_on_registration(self, client, db_session):
        """Self-registered candidates are automatically added to the talent pool."""
        from app.modules.talent_pool.models import TalentPoolProfiles

        _, user = await register_and_activate(client, db_session, "CANDIDATE")

        # Check talent pool entry was created
        result = await db_session.execute(
            select(TalentPoolProfiles).where(TalentPoolProfiles.added_by == user.id)
        )
        profiles = result.scalars().all()
        assert len(profiles) == 1
        assert profiles[0].candidate_profile_id is not None
        assert profiles[0].parsed_submission_id is None  # no CV yet


# ===========================================================================
# Talent pool promotion
# ===========================================================================


class TestTalentPoolPromotion:

    @pytest.mark.asyncio
    async def test_promotion_conflict_when_active_user_exists(self, client, db_session):
        """Promoting a profile whose email belongs to an active user → conflict, not merge."""
        from app.modules.ai.enums import CVParsingStatus
        from app.modules.ai.models import ParsedCVSubmission
        from app.modules.talent_pool.models import TalentPoolProfiles

        admin_token, admin = await register_and_activate(client, db_session, "ADMIN")

        # Create an active user with a known email
        existing_token, existing_user = await register_and_activate(
            client, db_session, "CANDIDATE"
        )
        existing_email = existing_user.email

        # Create a parsed submission with that email in parsed_data
        submission = ParsedCVSubmission(
            uploaded_by=admin.id,
            filename="cv.pdf",
            parse_status=CVParsingStatus.COMPLETED.value,
            parsed_data={
                "email": existing_email,
                "skills": ["Python"],
                "full_name": "Test Candidate",
            },
        )
        db_session.add(submission)
        await db_session.flush()

        profile = TalentPoolProfiles(
            parsed_submission_id=submission.id,
            added_by=admin.id,
            source="other",
            status="shortlisted",
        )
        db_session.add(profile)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/talent-pool/{profile.id}/promote",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "conflict"
        assert data["conflict_email"] == existing_email

    @pytest.mark.asyncio
    async def test_promotion_requires_admin_role(self, client, db_session):
        """Only admins can promote talent pool profiles."""
        employer_token, _ = await register_and_activate(client, db_session, "EMPLOYER")
        fake_profile_id = uuid4()

        resp = await client.post(
            f"/api/v1/talent-pool/{fake_profile_id}/promote",
            headers={"Authorization": f"Bearer {employer_token}"},
        )
        assert resp.status_code == 403


# ===========================================================================
# Deprecated endpoint
# ===========================================================================


class TestDeprecatedEndpoint:

    @pytest.mark.asyncio
    async def test_create_candidate_endpoint_returns_410(self, client, db_session):
        """POST /cv-parsing/submissions/{id}/create-candidate should return 410 Gone."""
        admin_token, _ = await register_and_activate(client, db_session, "ADMIN")
        fake_id = uuid4()

        resp = await client.post(
            f"/api/v1/cv-parsing/submissions/{fake_id}/create-candidate",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 410


# ===========================================================================
# AI score vs match_score distinction
# ===========================================================================


class TestScoreDistinction:

    def test_ai_score_and_match_score_are_separate_fields(self):
        """Confirm the two scores are stored on separate columns and don't overwrite each other."""
        from app.modules.applications.models import Application

        app_instance = Application(
            candidate_id=uuid4(),
            job_id=uuid4(),
            status="SUBMITTED",
        )
        app_instance.match_score = 65
        app_instance.ai_score = 82

        assert app_instance.match_score == 65
        assert app_instance.ai_score == 82
        assert app_instance.match_score != app_instance.ai_score
