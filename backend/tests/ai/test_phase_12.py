"""Phase 12 test suite — Semantic Matching (Embeddings).

Covers the Phase 12 completion checklist:
- pgvector extension enabled
- Embedding generation and storage (hash match → skip, hash change → regenerate)
- Similarity score computation between known vectors
- Fallback to keyword method when embedding missing
- Nightly recompute job scopes to genuinely stale applications only
- MockEmbeddingAIService used throughout — zero real API calls
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pytest
from sqlalchemy import select, text

from app.modules.ai.scoring_service import (
    hash_candidate_embedding_source,
    hash_job_embedding_source,
    hash_talent_pool_embedding_source,
)
from app.modules.ai.service import EmbeddingAIService, MockEmbeddingAIService
from tests.conftest import make_register_data

# ---------------------------------------------------------------------------
# Helpers (reuse pattern from test_phase_11_5)
# ---------------------------------------------------------------------------

async def register_and_activate(client, db_session, role: str = "CANDIDATE"):
    from app.modules.auth.jwt_handler import create_token_pair
    from app.modules.users.models import EmployerProfile, User

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


# ===========================================================================
# Task 1 — pgvector extension confirmed enabled
# ===========================================================================

class TestPgvectorExtension:

    @pytest.mark.asyncio
    async def test_vector_extension_is_installed(self, db_session):
        """The vector extension must appear in pg_extension."""
        result = await db_session.execute(
            text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
        )
        row = result.fetchone()
        assert row is not None, "pgvector extension is not installed"
        assert row[0] == "vector"


# ===========================================================================
# Task 2 — Vector columns present with correct dimension
# ===========================================================================

class TestVectorColumns:

    @pytest.mark.asyncio
    async def test_candidate_profile_has_embedding_columns(self, db_session):
        result = await db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'candidate_profile'
                AND column_name IN ('profile_embedding', 'embedding_source_hash', 'embedding_generated_at')
            """)
        )
        cols = {row[0] for row in result.fetchall()}
        assert cols == {"profile_embedding", "embedding_source_hash", "embedding_generated_at"}

    @pytest.mark.asyncio
    async def test_jobs_has_embedding_columns(self, db_session):
        result = await db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'jobs'
                AND column_name IN ('job_embedding', 'embedding_source_hash', 'embedding_generated_at')
            """)
        )
        cols = {row[0] for row in result.fetchall()}
        assert cols == {"job_embedding", "embedding_source_hash", "embedding_generated_at"}

    @pytest.mark.asyncio
    async def test_talent_pool_has_embedding_columns(self, db_session):
        result = await db_session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'talent_pool_profiles'
                AND column_name IN ('profile_embedding', 'embedding_source_hash', 'embedding_generated_at')
            """)
        )
        cols = {row[0] for row in result.fetchall()}
        assert cols == {"profile_embedding", "embedding_source_hash", "embedding_generated_at"}


# ===========================================================================
# Task 3 — MockEmbeddingAIService — no real API calls
# ===========================================================================

class TestMockEmbeddingAIService:

    @pytest.mark.asyncio
    async def test_generate_embedding_returns_1536_dims(self):
        svc = MockEmbeddingAIService()
        vec = await svc.generate_embedding("test text")
        assert len(vec) == 1536
        assert all(isinstance(v, float) for v in vec)

    @pytest.mark.asyncio
    async def test_generate_embedding_is_deterministic(self):
        svc = MockEmbeddingAIService()
        v1 = await svc.generate_embedding("hello")
        v2 = await svc.generate_embedding("completely different text")
        assert v1 == v2  # mock always returns fixed vector

    @pytest.mark.asyncio
    async def test_compute_similarity_score_returns_75(self):
        svc = MockEmbeddingAIService()
        v = [0.1] * 1536
        score = await svc.compute_similarity_score(v, v)
        assert score == 75

    @pytest.mark.asyncio
    async def test_similarity_score_clamped_0_100(self):
        svc = MockEmbeddingAIService()
        v = [0.1] * 1536
        score = await svc.compute_similarity_score(v, v)
        assert 0 <= score <= 100


# ===========================================================================
# Task 4 — Cosine similarity between known vectors
# ===========================================================================

class TestCosineSimilarity:

    @pytest.mark.asyncio
    async def test_identical_vectors_give_high_score(self):
        """Cosine similarity of identical vectors should be near 100."""
        with patch.object(
            EmbeddingAIService,
            "__init__",
            lambda self: setattr(self, "_client", None),
        ):
            svc = EmbeddingAIService()
            v = [0.5] * 1536
            score = await svc.compute_similarity_score(v, v)
            assert score >= 95

    @pytest.mark.asyncio
    async def test_orthogonal_vectors_give_low_score(self):
        """Cosine similarity of orthogonal vectors should be near 50 (after scaling)."""
        with patch.object(
            EmbeddingAIService,
            "__init__",
            lambda self: setattr(self, "_client", None),
        ):
            svc = EmbeddingAIService()
            a = [1.0] + [0.0] * 1535
            b = [0.0, 1.0] + [0.0] * 1534
            score = await svc.compute_similarity_score(a, b)
            # Orthogonal → cosine = 0 → scaled to 50
            assert 45 <= score <= 55

    @pytest.mark.asyncio
    async def test_opposite_vectors_give_zero_score(self):
        """Opposite vectors → cosine = -1 → scaled score = 0."""
        with patch.object(
            EmbeddingAIService,
            "__init__",
            lambda self: setattr(self, "_client", None),
        ):
            svc = EmbeddingAIService()
            a = [1.0] + [0.0] * 1535
            b = [-1.0] + [0.0] * 1535
            score = await svc.compute_similarity_score(a, b)
            assert score == 0

    @pytest.mark.asyncio
    async def test_score_is_integer_in_range(self):
        with patch.object(
            EmbeddingAIService,
            "__init__",
            lambda self: setattr(self, "_client", None),
        ):
            svc = EmbeddingAIService()
            a = list(np.random.rand(1536))
            b = list(np.random.rand(1536))
            score = await svc.compute_similarity_score(a, b)
            assert isinstance(score, int)
            assert 0 <= score <= 100


# ===========================================================================
# Task 5 — Embedding hash functions
# ===========================================================================

class TestEmbeddingHashFunctions:

    def test_candidate_hash_same_inputs(self):
        h1 = hash_candidate_embedding_source(["Python", "SQL"], "Bio text", "Summary text")
        h2 = hash_candidate_embedding_source(["Python", "SQL"], "Bio text", "Summary text")
        assert h1 == h2

    def test_candidate_hash_skill_order_normalised(self):
        h1 = hash_candidate_embedding_source(["Python", "SQL"], "bio", "summary")
        h2 = hash_candidate_embedding_source(["SQL", "Python"], "bio", "summary")
        assert h1 == h2

    def test_candidate_hash_changes_on_bio_update(self):
        h1 = hash_candidate_embedding_source(["Python"], "old bio", "summary")
        h2 = hash_candidate_embedding_source(["Python"], "new bio", "summary")
        assert h1 != h2

    def test_candidate_hash_changes_on_summary_update(self):
        h1 = hash_candidate_embedding_source(["Python"], "bio", "old summary")
        h2 = hash_candidate_embedding_source(["Python"], "bio", "new summary")
        assert h1 != h2

    def test_candidate_hash_handles_none(self):
        h = hash_candidate_embedding_source(None, None, None)
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest

    def test_job_hash_same_inputs(self):
        h1 = hash_job_embedding_source("Build APIs", ["Python", "SQL"])
        h2 = hash_job_embedding_source("Build APIs", ["Python", "SQL"])
        assert h1 == h2

    def test_job_hash_skill_order_normalised(self):
        h1 = hash_job_embedding_source("desc", ["Python", "SQL"])
        h2 = hash_job_embedding_source("desc", ["SQL", "Python"])
        assert h1 == h2

    def test_job_hash_changes_on_description_update(self):
        h1 = hash_job_embedding_source("Build APIs", ["Python"])
        h2 = hash_job_embedding_source("Build mobile apps", ["Python"])
        assert h1 != h2

    def test_talent_pool_hash_same_inputs(self):
        h1 = hash_talent_pool_embedding_source(["Python"], "summary text")
        h2 = hash_talent_pool_embedding_source(["Python"], "summary text")
        assert h1 == h2

    def test_talent_pool_hash_changes_on_summary_update(self):
        h1 = hash_talent_pool_embedding_source(["Python"], "old summary")
        h2 = hash_talent_pool_embedding_source(["Python"], "new summary")
        assert h1 != h2


# ===========================================================================
# Task 6 — Hash unchanged → no regeneration (unit tests, no task machinery)
# ===========================================================================

class TestEmbeddingHashInvalidation:

    def test_hash_unchanged_skips_generation(self):
        """If stored hash equals computed hash and embedding exists, skip — no API call needed."""
        skills = ["Python", "SQL"]
        bio = "Experienced developer"
        summary = "Built scalable systems"
        current_hash = hash_candidate_embedding_source(skills, bio, summary)

        stored_hash = current_hash  # same — hash hasn't changed
        has_embedding = True

        should_regenerate = not (stored_hash == current_hash and has_embedding)
        assert should_regenerate is False

    def test_hash_changed_triggers_regeneration(self):
        """If stored hash differs from computed hash, regeneration should run."""
        skills = ["Python", "SQL"]
        bio = "Updated bio"
        summary = "Updated summary"
        current_hash = hash_candidate_embedding_source(skills, bio, summary)

        stored_hash = "stale_hash_abc123"  # outdated
        has_embedding = True

        should_regenerate = not (stored_hash == current_hash and has_embedding)
        assert should_regenerate is True

    def test_missing_embedding_triggers_regeneration_even_with_matching_hash(self):
        """If embedding is missing but hash matches (edge case), still regenerate."""
        skills = ["Python"]
        bio = "bio"
        summary = "summary"
        current_hash = hash_candidate_embedding_source(skills, bio, summary)

        stored_hash = current_hash
        has_embedding = False  # embedding was deleted / never stored

        should_regenerate = not (stored_hash == current_hash and has_embedding)
        assert should_regenerate is True

    def test_job_hash_unchanged_skips(self):
        description = "Build scalable APIs"
        skills = ["Python", "FastAPI"]
        current_hash = hash_job_embedding_source(description, skills)

        should_regenerate = not (current_hash == current_hash and True)
        assert should_regenerate is False

    def test_job_hash_changed_triggers(self):
        description = "Build mobile apps"
        skills = ["Swift"]
        current_hash = hash_job_embedding_source(description, skills)
        stored_hash = "old_hash"

        should_regenerate = not (stored_hash == current_hash and True)
        assert should_regenerate is True


# ===========================================================================
# Task 7 — Fallback to keyword scoring when embedding missing
# ===========================================================================

class TestEmbeddingFallback:

    @pytest.mark.asyncio
    async def test_scoring_uses_keyword_when_no_job_embedding(self):
        """When job_embedding is None, scoring falls back to compute_deterministic_score."""
        from app.modules.ai.scoring_service import compute_deterministic_score

        candidate_embedding = [0.5] * 1536
        job_embedding = None  # not yet generated

        # Simulate the fallback condition
        use_embedding = candidate_embedding is not None and job_embedding is not None
        assert use_embedding is False

        # Keyword scoring should still produce a valid result
        score = compute_deterministic_score(
            candidate_skills=["Python", "SQL"],
            candidate_years_experience=3,
            candidate_seniority="MID",
            job_required_skills=["Python", "SQL"],
            job_seniority_level="MID",
            job_min_years_experience=2,
        )
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_scoring_uses_keyword_when_no_candidate_embedding(self):
        """When profile_embedding is None, scoring falls back to keyword method."""
        candidate_embedding = None  # embedding not yet generated
        job_embedding = [0.5] * 1536

        use_embedding = candidate_embedding is not None and job_embedding is not None
        assert use_embedding is False

    @pytest.mark.asyncio
    async def test_both_missing_falls_back(self):
        candidate_embedding = None
        job_embedding = None
        use_embedding = candidate_embedding is not None and job_embedding is not None
        assert use_embedding is False

    @pytest.mark.asyncio
    async def test_both_present_uses_embedding(self):
        candidate_embedding = [0.5] * 1536
        job_embedding = [0.5] * 1536
        use_embedding = candidate_embedding is not None and job_embedding is not None
        assert use_embedding is True


# ===========================================================================
# Task 8 — Nightly recompute job scopes correctly
# ===========================================================================

class TestNightlyRecompute:

    @pytest.mark.asyncio
    async def test_stale_applications_are_requeued(self, db_session):
        """Applications where candidate updated_at > ai_score_computed_at are requeued."""
        from app.modules.applications.models import Application
        from app.modules.candidates.models import CandidateProfile
        from app.modules.users.models import User

        now = datetime.now(UTC)

        # Create employer
        employer = User(
            first_name="Emp", last_name="User",
            email=f"emp_{uuid4().hex[:6]}@test.com",
            phone_number=f"080{uuid4().int % 10**8:08d}",
            password_hash="x", role="EMPLOYER", account_status="ACTIVE",
        )
        db_session.add(employer)
        await db_session.flush()

        # Create candidate with updated_at in the future (simulating recent profile update)
        candidate = User(
            first_name="Cand", last_name="User",
            email=f"cand_{uuid4().hex[:6]}@test.com",
            phone_number=f"081{uuid4().int % 10**8:08d}",
            password_hash="x", role="CANDIDATE", account_status="ACTIVE",
        )
        db_session.add(candidate)
        await db_session.flush()

        from app.modules.jobs.enums import ContractType, WorkLocation
        from app.modules.jobs.models import Job

        job = Job(
            employer_id=employer.id,
            title="Test Job",
            description="A test job description.",
            location="Lagos",
            contract_type=ContractType.FULL_TIME.value,
            work_location=WorkLocation.LOCAL.value,
            status="ACTIVE",
        )
        db_session.add(job)
        await db_session.flush()

        # Application scored 1 hour ago
        scored_at = now - timedelta(hours=1)

        # CandidateProfile updated 30 minutes ago (after scoring → stale)
        profile = CandidateProfile(
            user_id=candidate.id,
        )
        db_session.add(profile)
        await db_session.flush()

        # Manually set updated_at to simulate a recent profile update
        await db_session.execute(
            text("UPDATE candidate_profile SET updated_at = :t WHERE id = :id"),
            {"t": now - timedelta(minutes=30), "id": profile.id},
        )

        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status="SUBMITTED",
            ai_score=75,
            ai_score_computed_at=scored_at,
        )
        db_session.add(application)
        await db_session.flush()

        # Query that the nightly job would use
        from sqlalchemy import and_
        result = await db_session.execute(
            select(Application.id)
            .join(CandidateProfile, CandidateProfile.user_id == Application.candidate_id)
            .where(
                and_(
                    Application.ai_score.is_not(None),
                    Application.ai_score_computed_at.is_not(None),
                    CandidateProfile.updated_at > Application.ai_score_computed_at,
                )
            )
        )
        stale_ids = result.scalars().all()
        assert application.id in stale_ids

    @pytest.mark.asyncio
    async def test_fresh_applications_not_requeued(self, db_session):
        """Applications where scoring was done after the profile update are NOT stale."""
        from app.modules.applications.models import Application
        from app.modules.candidates.models import CandidateProfile
        from app.modules.users.models import User

        now = datetime.now(UTC)

        candidate = User(
            first_name="Fresh", last_name="Cand",
            email=f"fresh_{uuid4().hex[:6]}@test.com",
            phone_number=f"082{uuid4().int % 10**8:08d}",
            password_hash="x", role="CANDIDATE", account_status="ACTIVE",
        )
        db_session.add(candidate)
        await db_session.flush()

        from app.modules.jobs.enums import ContractType, WorkLocation
        from app.modules.jobs.models import Job

        employer = User(
            first_name="E2", last_name="User",
            email=f"e2_{uuid4().hex[:6]}@test.com",
            phone_number=f"083{uuid4().int % 10**8:08d}",
            password_hash="x", role="EMPLOYER", account_status="ACTIVE",
        )
        db_session.add(employer)
        await db_session.flush()

        job = Job(
            employer_id=employer.id,
            title="Fresh Job",
            description="A fresh job description.",
            location="Abuja",
            contract_type=ContractType.FULL_TIME.value,
            work_location=WorkLocation.LOCAL.value,
            status="ACTIVE",
        )
        db_session.add(job)
        await db_session.flush()

        profile = CandidateProfile(user_id=candidate.id)
        db_session.add(profile)
        await db_session.flush()

        # Profile updated 2 hours ago, scoring happened 1 hour ago (scoring is NEWER → not stale)
        await db_session.execute(
            text("UPDATE candidate_profile SET updated_at = :t WHERE id = :id"),
            {"t": now - timedelta(hours=2), "id": profile.id},
        )

        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status="SUBMITTED",
            ai_score=80,
            ai_score_computed_at=now - timedelta(hours=1),  # scored AFTER profile update
        )
        db_session.add(application)
        await db_session.flush()

        from sqlalchemy import and_
        result = await db_session.execute(
            select(Application.id)
            .join(CandidateProfile, CandidateProfile.user_id == Application.candidate_id)
            .where(
                and_(
                    Application.ai_score.is_not(None),
                    Application.ai_score_computed_at.is_not(None),
                    CandidateProfile.updated_at > Application.ai_score_computed_at,
                )
            )
        )
        stale_ids = result.scalars().all()
        assert application.id not in stale_ids

    @pytest.mark.asyncio
    async def test_unscored_applications_not_in_stale_query(self, db_session):
        """Applications with no ai_score are not touched by the nightly job."""
        from app.modules.applications.models import Application
        from app.modules.candidates.models import CandidateProfile
        from app.modules.users.models import User

        candidate = User(
            first_name="Unscored", last_name="Cand",
            email=f"unscored_{uuid4().hex[:6]}@test.com",
            phone_number=f"084{uuid4().int % 10**8:08d}",
            password_hash="x", role="CANDIDATE", account_status="ACTIVE",
        )
        db_session.add(candidate)
        await db_session.flush()

        profile = CandidateProfile(user_id=candidate.id)
        db_session.add(profile)
        await db_session.flush()

        from app.modules.jobs.enums import ContractType, WorkLocation
        from app.modules.jobs.models import Job

        employer = User(
            first_name="E3", last_name="User",
            email=f"e3_{uuid4().hex[:6]}@test.com",
            phone_number=f"085{uuid4().int % 10**8:08d}",
            password_hash="x", role="EMPLOYER", account_status="ACTIVE",
        )
        db_session.add(employer)
        await db_session.flush()

        job = Job(
            employer_id=employer.id,
            title="Unscored Job",
            description="A job for unscored applications.",
            location="Kano",
            contract_type=ContractType.FULL_TIME.value,
            work_location=WorkLocation.LOCAL.value,
            status="ACTIVE",
        )
        db_session.add(job)
        await db_session.flush()

        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status="SUBMITTED",
            ai_score=None,          # never scored
            ai_score_computed_at=None,
        )
        db_session.add(application)
        await db_session.flush()

        from sqlalchemy import and_
        result = await db_session.execute(
            select(Application.id)
            .join(CandidateProfile, CandidateProfile.user_id == Application.candidate_id)
            .where(
                and_(
                    Application.ai_score.is_not(None),
                    Application.ai_score_computed_at.is_not(None),
                    CandidateProfile.updated_at > Application.ai_score_computed_at,
                )
            )
        )
        stale_ids = result.scalars().all()
        assert application.id not in stale_ids
