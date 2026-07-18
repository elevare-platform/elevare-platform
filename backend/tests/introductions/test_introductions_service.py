"""Tests for IntroductionService — create, accept, decline, lazy expiry, refund."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationException
from app.modules.credits.service import CreditsService
from app.modules.introductions.enums import IntroductionStatus
from app.modules.introductions.models import IntroductionRequest
from app.modules.introductions.service import (
    IntroductionService,
    _resolve_candidate_email,
)
from app.modules.talent_pool.enums import SourceType, TalentPoolStatus
from app.modules.talent_pool.models import TalentPoolProfiles
from tests.conftest import make_employer, make_job


def make_talent_pool_profile(employer_id, job_id, **overrides):
    defaults = {
        "source": SourceType.OTHER.value,
        "added_by": employer_id,
        "sourced_for_job_id": job_id,
        "status": TalentPoolStatus.NEW.value,
    }
    defaults.update(overrides)
    return TalentPoolProfiles(**defaults)


def make_intro_request(employer_id, job_id, profile_id, **overrides):
    defaults = {
        "employer_id": employer_id,
        "job_id": job_id,
        "talent_pool_profile_id": profile_id,
        "status": IntroductionStatus.PENDING.value,
        "token": "test-token-abc123",
        "expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    defaults.update(overrides)
    return IntroductionRequest(**defaults)


def _profile_mock(email="candidate@test.com"):
    m = MagicMock()
    m.candidate_profile = None
    m.parsed_submission.parsed_data = {"email": email}
    return m


# _resolve_candidate_email


def test_resolve_email_self_registered():
    profile = MagicMock()
    profile.candidate_profile.user.email = "candidate@example.com"
    profile.parsed_submission = None
    assert _resolve_candidate_email(profile) == "candidate@example.com"


def test_resolve_email_sourced_only():
    profile = MagicMock()
    profile.candidate_profile = None
    profile.parsed_submission.parsed_data = {"email": "sourced@example.com"}
    assert _resolve_candidate_email(profile) == "sourced@example.com"


def test_resolve_email_returns_none_when_no_email():
    profile = MagicMock()
    profile.candidate_profile = None
    profile.parsed_submission = None
    assert _resolve_candidate_email(profile) is None


# request_introduction


@pytest.mark.asyncio
async def test_request_introduction_deducts_credit_and_creates_row(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    credits_service = CreditsService(db_session)
    await credits_service.grant(employer.id, amount=3)

    service = IntroductionService(db_session)

    mock_task = MagicMock()
    mock_task.delay = MagicMock()

    with patch(
        "app.modules.introductions.tasks.send_introduction_request_email", mock_task
    ):
        with patch(
            "app.modules.introductions.service.TalentPoolRepository.get_by_id_joined_with_parsed_data",
            return_value=_profile_mock(),
        ):
            result = await service.request_introduction(
                employer_id=employer.id,
                job_id=job.id,
                talent_pool_profile_id=profile.id,
            )

    assert result.status == IntroductionStatus.PENDING.value
    assert result.employer_id == employer.id
    assert await credits_service.get_balance(employer.id) == 2


@pytest.mark.asyncio
async def test_request_introduction_raises_when_no_credits(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    service = IntroductionService(db_session)

    with pytest.raises(ValidationException, match="Insufficient credits"):
        with patch(
            "app.modules.introductions.service.TalentPoolRepository.get_by_id_joined_with_parsed_data",
            return_value=_profile_mock(),
        ):
            await service.request_introduction(
                employer_id=employer.id,
                job_id=job.id,
                talent_pool_profile_id=profile.id,
            )


@pytest.mark.asyncio
async def test_request_introduction_raises_on_duplicate_pending(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    existing = make_intro_request(employer.id, job.id, profile.id)
    db_session.add(existing)
    await db_session.flush()

    credits_service = CreditsService(db_session)
    await credits_service.grant(employer.id, amount=3)

    service = IntroductionService(db_session)

    with pytest.raises(ValidationException, match="already pending"):
        with patch(
            "app.modules.introductions.service.TalentPoolRepository.get_by_id_joined_with_parsed_data",
            return_value=_profile_mock(),
        ):
            await service.request_introduction(
                employer_id=employer.id,
                job_id=job.id,
                talent_pool_profile_id=profile.id,
            )


# accept


@pytest.mark.asyncio
async def test_accept_marks_accepted(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    intro = make_intro_request(employer.id, job.id, profile.id, token="accept-token-1")
    db_session.add(intro)
    await db_session.flush()

    result = await IntroductionService(db_session).accept("accept-token-1")

    assert result["status"] == "ACCEPTED"
    await db_session.refresh(intro)
    assert intro.status == IntroductionStatus.ACCEPTED.value
    assert intro.responded_at is not None


@pytest.mark.asyncio
async def test_accept_already_used_returns_status(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    intro = make_intro_request(
        employer.id,
        job.id,
        profile.id,
        token="used-token-1",
        status=IntroductionStatus.ACCEPTED.value,
    )
    db_session.add(intro)
    await db_session.flush()

    result = await IntroductionService(db_session).accept("used-token-1")
    assert result["status"] == IntroductionStatus.ACCEPTED.value


# decline + refund


@pytest.mark.asyncio
async def test_decline_marks_declined_and_refunds_credit(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    intro = make_intro_request(employer.id, job.id, profile.id, token="decline-token-1")
    db_session.add(intro)
    await db_session.flush()

    credits_service = CreditsService(db_session)
    await credits_service.grant(employer.id, amount=2)
    await credits_service.deduct(employer.id)

    result = await IntroductionService(db_session).decline("decline-token-1")

    assert result["status"] == "DECLINED"
    await db_session.refresh(intro)
    assert intro.status == IntroductionStatus.DECLINED.value
    assert intro.responded_at is not None
    assert await credits_service.get_balance(employer.id) == 2


# lazy expiry


@pytest.mark.asyncio
async def test_expired_token_refunds_credit_on_accept(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    intro = make_intro_request(
        employer.id,
        job.id,
        profile.id,
        token="expired-token-1",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(intro)
    await db_session.flush()

    credits_service = CreditsService(db_session)
    await credits_service.grant(employer.id, amount=1)
    await credits_service.deduct(employer.id)

    result = await IntroductionService(db_session).accept("expired-token-1")

    assert result["status"] == "EXPIRED"
    assert await credits_service.get_balance(employer.id) == 1


@pytest.mark.asyncio
async def test_expired_token_refunds_credit_on_decline(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()

    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    profile = make_talent_pool_profile(employer.id, job.id)
    db_session.add(profile)
    await db_session.flush()

    intro = make_intro_request(
        employer.id,
        job.id,
        profile.id,
        token="expired-token-2",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(intro)
    await db_session.flush()

    credits_service = CreditsService(db_session)
    await credits_service.grant(employer.id, amount=1)
    await credits_service.deduct(employer.id)

    result = await IntroductionService(db_session).decline("expired-token-2")

    assert result["status"] == "EXPIRED"
    assert await credits_service.get_balance(employer.id) == 1
