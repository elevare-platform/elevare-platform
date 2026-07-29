"""Tests for AccessTokenService — job access tokens and the public applicant view."""

from unittest.mock import patch

import pytest

from app.core.storage import MockStorageService
from app.modules.applications.models import Application
from app.modules.candidates.models import CandidateCvs, CandidateProfile
from app.modules.jobs.access_token_schema import CreateAccessTokenRequest
from app.modules.jobs.access_token_service import AccessTokenService
from app.modules.users.enums import UserRole
from app.modules.users.models import User
from tests.conftest import make_employer, make_job, make_user


def make_candidate(**overrides) -> User:
    """Build an unsaved candidate User instance."""
    return make_user(role=UserRole.CANDIDATE.value, **overrides)


@pytest.fixture(autouse=True)
def mock_storage():
    """Force MockStorageService for every test in this module — no real R2 calls."""
    with patch(
        "app.modules.jobs.access_token_service.get_storage_service",
        return_value=MockStorageService(),
    ):
        yield


async def _create_token(db_session, job, employer, **overrides) -> str:
    """Create an access token via the service and return its raw token string."""
    from app.modules.jobs.access_token_repository import AccessTokenRepository

    service = AccessTokenService(db_session)
    data = CreateAccessTokenRequest(
        expires_in_days=7,
        disclose_names=overrides.get("disclose_names", False),
        show_cv=overrides.get("show_cv", False),
    )
    response = await service.create_access_token(job.id, data, employer)
    repo = AccessTokenRepository(db_session)
    token = await repo.get_by_id(response.id)
    return token.token


@pytest.mark.asyncio
async def test_create_access_token_persists_show_cv(db_session):
    """create_access_token stores show_cv and reflects it in the response."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    service = AccessTokenService(db_session)
    data = CreateAccessTokenRequest(expires_in_days=7, show_cv=True)
    result = await service.create_access_token(job.id, data, employer)

    assert result.show_cv is True


@pytest.mark.asyncio
async def test_create_access_token_defaults_show_cv_false(db_session):
    """create_access_token defaults show_cv to False when omitted."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    service = AccessTokenService(db_session)
    data = CreateAccessTokenRequest(expires_in_days=7)
    result = await service.create_access_token(job.id, data, employer)

    assert result.show_cv is False


async def _make_platform_applicant(db_session, job, *, cv_sharing_consent: bool):
    """Create a candidate with a CV and an application to `job`."""
    candidate = make_candidate()
    db_session.add(candidate)
    await db_session.flush()

    profile = CandidateProfile(
        user_id=candidate.id,
        cv_sharing_consent=cv_sharing_consent,
    )
    db_session.add(profile)
    await db_session.flush()

    cv = CandidateCvs(
        candidate_id=profile.id,
        key="cv-files/some-candidate.pdf",
        filename="resume.pdf",
    )
    db_session.add(cv)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        cv_id=cv.id,
        ai_score=80,
    )
    db_session.add(application)
    await db_session.flush()

    return candidate, application, cv


@pytest.mark.asyncio
async def test_public_applicants_hides_cv_when_show_cv_false(db_session):
    """cv_download_url stays None for platform applicants when the token has show_cv=False."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    await _make_platform_applicant(db_session, job, cv_sharing_consent=True)

    token_str = await _create_token(db_session, job, employer, show_cv=False)

    service = AccessTokenService(db_session)
    result = await service.get_public_applicants(token_str)

    assert result.applicants[0].cv_download_url is None


@pytest.mark.asyncio
async def test_public_applicants_shows_cv_when_show_cv_and_consent(db_session):
    """cv_download_url is populated when show_cv=True AND the candidate consented."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    _, _, cv = await _make_platform_applicant(db_session, job, cv_sharing_consent=True)

    token_str = await _create_token(db_session, job, employer, show_cv=True)

    service = AccessTokenService(db_session)
    result = await service.get_public_applicants(token_str)

    assert result.applicants[0].cv_download_url == f"https://mock-storage/{cv.key}"


@pytest.mark.asyncio
async def test_public_applicants_hides_cv_when_show_cv_true_but_no_consent(db_session):
    """show_cv=True does not override a candidate's cv_sharing_consent=False."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    await _make_platform_applicant(db_session, job, cv_sharing_consent=False)

    token_str = await _create_token(db_session, job, employer, show_cv=True)

    service = AccessTokenService(db_session)
    result = await service.get_public_applicants(token_str)

    assert result.applicants[0].cv_download_url is None


async def _make_external_profile(
    db_session, job, added_by_id, *, ai_score: int = 70, r2_key: str = "external/cv.pdf"
):
    from app.modules.ai.models import ParsedCVSubmission
    from app.modules.talent_pool.models import TalentPoolProfiles

    submission = ParsedCVSubmission(
        filename="external.pdf",
        r2_key=r2_key,
        parsed_data={"summary": "External candidate summary."},
    )
    db_session.add(submission)
    await db_session.flush()

    profile = TalentPoolProfiles(
        parsed_submission_id=submission.id,
        sourced_for_job_id=job.id,
        added_by=added_by_id,
        ai_score=ai_score,
    )
    db_session.add(profile)
    await db_session.flush()

    return profile, submission


@pytest.mark.asyncio
async def test_public_applicants_shows_external_cv_when_show_cv_true(db_session):
    """External talent-pool CVs are exposed once show_cv=True — no consent gate applies."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    _, submission = await _make_external_profile(db_session, job, employer.id)

    token_str = await _create_token(db_session, job, employer, show_cv=True)

    service = AccessTokenService(db_session)
    result = await service.get_public_applicants(token_str)

    external = next(a for a in result.applicants if a.source == "external")
    assert external.cv_download_url == f"https://mock-storage/{submission.r2_key}"


@pytest.mark.asyncio
async def test_public_applicants_hides_external_cv_when_show_cv_false(db_session):
    """External CVs stay hidden when the token has show_cv=False."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    await _make_external_profile(db_session, job, employer.id)

    token_str = await _create_token(db_session, job, employer, show_cv=False)

    service = AccessTokenService(db_session)
    result = await service.get_public_applicants(token_str)

    external = next(a for a in result.applicants if a.source == "external")
    assert external.cv_download_url is None


@pytest.mark.asyncio
async def test_public_applicants_cv_snippet_still_populated(db_session):
    """Regression guard: cv_snippet keeps working for platform applicants (was dead code)."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    from app.modules.ai.models import ParsedCVSubmission

    candidate = make_candidate()
    db_session.add(candidate)
    await db_session.flush()

    profile = CandidateProfile(user_id=candidate.id, cv_sharing_consent=True)
    db_session.add(profile)
    await db_session.flush()

    submission = ParsedCVSubmission(
        filename="resume.pdf",
        r2_key="cv-files/resume.pdf",
        parsed_data={"summary": "A great candidate summary."},
    )
    db_session.add(submission)
    await db_session.flush()

    cv = CandidateCvs(
        candidate_id=profile.id,
        key="cv-files/resume.pdf",
        filename="resume.pdf",
        submission_id=submission.id,
    )
    db_session.add(cv)
    await db_session.flush()

    application = Application(
        candidate_id=candidate.id, job_id=job.id, cv_id=cv.id, ai_score=90
    )
    db_session.add(application)
    await db_session.flush()

    token_str = await _create_token(db_session, job, employer, show_cv=False)

    service = AccessTokenService(db_session)
    result = await service.get_public_applicants(token_str)

    assert result.applicants[0].cv_snippet == "A great candidate summary."
