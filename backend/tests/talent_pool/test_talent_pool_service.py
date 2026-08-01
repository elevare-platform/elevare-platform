"""Tests for the on-demand talent-pool scoring endpoint and the AI-match
staleness fix — both shipped together as part of the AI Talent Match
"score against this job" feature.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import (
    JobNotFoundError,
    PermissionDeniedException,
    ProfileNotFoundException,
)
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.ai.scoring_service import hash_job_scoring_inputs
from app.modules.jobs.enums import ContractType, WorkModel
from app.modules.jobs.schemas import build_full_description
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.service import TalentPoolService
from app.modules.users.models import EmployerProfile, User
from tests.conftest import make_job
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
            kyc_status="APPROVED",
        )
        db_session.add(profile)
        await db_session.flush()
    token_pair = create_token_pair(user.id, role)
    return token_pair["access_token"], user


def current_job_hash(job) -> str:
    """Compute the same hash get_job_matches/score_profile_against_job use."""
    return hash_job_scoring_inputs(
        build_full_description(
            about_the_role=job.about_the_role,
            key_responsibilities=job.key_responsibilities,
            requirements=job.requirements,
            preferred_certifications=job.preferred_certifications,
            technical_competencies=job.technical_competencies,
            what_we_offer=job.what_we_offer,
            legacy_description=job.description,
        ),
        job.required_skills or [],
        job.seniority_level,
    )


async def make_sourced_profile(db_session, added_by, ai_score_job_hash=None) -> TalentPoolProfiles:
    """A sourced (non-self-registered) talent pool profile with a parsed CV."""
    submission = ParsedCVSubmission(
        uploaded_by=added_by,
        filename="cv.pdf",
        parse_status=CVParsingStatus.COMPLETED.value,
        parsed_data={"skills": ["Python"], "full_name": "Test Candidate"},
    )
    db_session.add(submission)
    await db_session.flush()

    profile = TalentPoolProfiles(
        parsed_submission_id=submission.id,
        added_by=added_by,
        source="other",
        status="new",
        ai_score_job_hash=ai_score_job_hash,
        ai_fit_summary="Strong fit for a different role entirely."
        if ai_score_job_hash
        else None,
        ai_strengths=["Strong Python skills"] if ai_score_job_hash else None,
        ai_weaknesses=["No cloud experience"] if ai_score_job_hash else None,
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


# ===========================================================================
# POST /talent-pool/{profile_id}/score — on-demand scoring
# ===========================================================================


class TestScoreProfileAgainstJobEndpoint:

    @pytest.mark.asyncio
    async def test_owner_employer_can_queue_scoring(self, client, db_session):
        token, employer = await register_and_activate(client, db_session, "EMPLOYER")
        job = make_job(employer.id, moderation_status="APPROVED")
        db_session.add(job)
        await db_session.flush()
        profile = await make_sourced_profile(db_session, added_by=employer.id)

        resp = await client.post(
            f"/api/v1/talent-pool/{profile.id}/score",
            params={"job_id": str(job.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"

    @pytest.mark.asyncio
    async def test_already_current_short_circuits_without_error(self, client, db_session):
        """A profile already scored against this exact job returns a plain
        dict, not a 500 — the original implementation returned a pydantic
        model where a `dict` return type was declared, which crashed."""
        token, employer = await register_and_activate(client, db_session, "EMPLOYER")
        job = make_job(employer.id, moderation_status="APPROVED")
        db_session.add(job)
        await db_session.flush()
        profile = await make_sourced_profile(
            db_session, added_by=employer.id, ai_score_job_hash=current_job_hash(job)
        )

        resp = await client.post(
            f"/api/v1/talent-pool/{profile.id}/score",
            params={"job_id": str(job.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 202
        assert resp.json()["status"] == "already_current"

    @pytest.mark.asyncio
    async def test_employer_cannot_score_against_a_job_they_do_not_own(
        self, client, db_session
    ):
        token, employer = await register_and_activate(client, db_session, "EMPLOYER")
        _, other_employer = await register_and_activate(client, db_session, "EMPLOYER")
        job = make_job(other_employer.id, moderation_status="APPROVED")
        db_session.add(job)
        await db_session.flush()
        profile = await make_sourced_profile(db_session, added_by=employer.id)

        resp = await client.post(
            f"/api/v1/talent-pool/{profile.id}/score",
            params={"job_id": str(job.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_can_score_against_any_job(self, client, db_session):
        admin_token, admin = await register_and_activate(client, db_session, "ADMIN")
        _, employer = await register_and_activate(client, db_session, "EMPLOYER")
        job = make_job(employer.id, moderation_status="APPROVED")
        db_session.add(job)
        await db_session.flush()
        profile = await make_sourced_profile(db_session, added_by=employer.id)

        resp = await client.post(
            f"/api/v1/talent-pool/{profile.id}/score",
            params={"job_id": str(job.id)},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"

    @pytest.mark.asyncio
    async def test_unknown_job_returns_404(self, client, db_session):
        token, employer = await register_and_activate(client, db_session, "EMPLOYER")
        profile = await make_sourced_profile(db_session, added_by=employer.id)

        resp = await client.post(
            f"/api/v1/talent-pool/{profile.id}/score",
            params={"job_id": str(uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_unknown_profile_returns_404(self, client, db_session):
        token, employer = await register_and_activate(client, db_session, "EMPLOYER")
        job = make_job(employer.id, moderation_status="APPROVED")
        db_session.add(job)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/talent-pool/{uuid4()}/score",
            params={"job_id": str(job.id)},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_candidate_role_is_forbidden(self, client, db_session):
        token, _candidate = await register_and_activate(client, db_session, "CANDIDATE")

        resp = await client.post(
            f"/api/v1/talent-pool/{uuid4()}/score",
            params={"job_id": str(uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 403


# ===========================================================================
# score_profile_against_job — service-level exception mapping
# ===========================================================================


class TestScoreProfileAgainstJobService:

    @pytest.mark.asyncio
    async def test_raises_profile_not_found(self, db_session):
        from tests.conftest import make_employer

        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()
        job = make_job(employer.id)
        db_session.add(job)
        await db_session.flush()

        service = TalentPoolService(db_session, cv_service=None)
        with pytest.raises(ProfileNotFoundException):
            await service.score_profile_against_job(uuid4(), job.id, employer)

    @pytest.mark.asyncio
    async def test_raises_job_not_found(self, db_session):
        from tests.conftest import make_employer

        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()
        profile = await make_sourced_profile(db_session, added_by=employer.id)

        service = TalentPoolService(db_session, cv_service=None)
        with pytest.raises(JobNotFoundError):
            await service.score_profile_against_job(profile.id, uuid4(), employer)

    @pytest.mark.asyncio
    async def test_raises_permission_denied_for_non_owner(self, db_session):
        from tests.conftest import make_employer

        employer = make_employer()
        other_employer = make_employer()
        db_session.add_all([employer, other_employer])
        await db_session.flush()
        job = make_job(other_employer.id)
        db_session.add(job)
        await db_session.flush()
        profile = await make_sourced_profile(db_session, added_by=employer.id)

        service = TalentPoolService(db_session, cv_service=None)
        with pytest.raises(PermissionDeniedException):
            await service.score_profile_against_job(profile.id, job.id, employer)


# ===========================================================================
# get_job_matches — stale AI reasoning must not leak across jobs
# ===========================================================================


class TestGetJobMatchesStaleness:

    @pytest.mark.asyncio
    async def test_ai_fit_summary_shown_when_hash_matches_current_job(
        self, db_session, monkeypatch
    ):
        from tests.conftest import make_employer

        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()
        job = make_job(employer.id, job_embedding=[0.0] * 1536)
        db_session.add(job)
        await db_session.flush()

        profile = await make_sourced_profile(
            db_session, added_by=employer.id, ai_score_job_hash=current_job_hash(job)
        )

        async def fake_top_matches(db, job_arg, employer_id, limit=20, exclude_user_ids=None):
            # find_matches_for_job (the real code path this replaces) eager-loads
            # these relationships via selectinload — mirror that so resolve_match_
            # display_fields' plain attribute access doesn't lazy-load outside a
            # greenlet context.
            from sqlalchemy.orm import selectinload

            loaded = (
                await db.execute(
                    select(TalentPoolProfiles)
                    .options(
                        selectinload(TalentPoolProfiles.parsed_submission),
                        selectinload(TalentPoolProfiles.candidate_profile),
                    )
                    .where(TalentPoolProfiles.id == profile.id)
                )
            ).scalar_one()
            return [(loaded, 80, [])]

        monkeypatch.setattr(
            "app.modules.talent_pool.service.get_top_matches_for_job", fake_top_matches
        )

        service = TalentPoolService(db_session, cv_service=None)
        result = await service.get_job_matches(job_id=job.id, employer_id=employer.id)

        assert len(result.items) == 1
        assert result.items[0].ai_fit_summary == profile.ai_fit_summary

    @pytest.mark.asyncio
    async def test_ai_fit_summary_hidden_when_scored_for_a_different_job(
        self, db_session, monkeypatch
    ):
        from tests.conftest import make_employer

        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()
        job = make_job(employer.id, job_embedding=[0.0] * 1536)
        db_session.add(job)
        await db_session.flush()

        # Scored against some other job's inputs — hash won't match this job.
        profile = await make_sourced_profile(
            db_session, added_by=employer.id, ai_score_job_hash="stale-hash-from-another-job"
        )

        async def fake_top_matches(db, job_arg, employer_id, limit=20, exclude_user_ids=None):
            # find_matches_for_job (the real code path this replaces) eager-loads
            # these relationships via selectinload — mirror that so resolve_match_
            # display_fields' plain attribute access doesn't lazy-load outside a
            # greenlet context.
            from sqlalchemy.orm import selectinload

            loaded = (
                await db.execute(
                    select(TalentPoolProfiles)
                    .options(
                        selectinload(TalentPoolProfiles.parsed_submission),
                        selectinload(TalentPoolProfiles.candidate_profile),
                    )
                    .where(TalentPoolProfiles.id == profile.id)
                )
            ).scalar_one()
            return [(loaded, 80, [])]

        monkeypatch.setattr(
            "app.modules.talent_pool.service.get_top_matches_for_job", fake_top_matches
        )

        service = TalentPoolService(db_session, cv_service=None)
        result = await service.get_job_matches(job_id=job.id, employer_id=employer.id)

        assert len(result.items) == 1
        assert result.items[0].ai_fit_summary is None
        assert result.items[0].ai_strengths is None
        assert result.items[0].ai_weaknesses is None
