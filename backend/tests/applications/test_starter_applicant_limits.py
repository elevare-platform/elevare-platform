"""A Starter job switches itself off when it takes its last allowed applicant.

Starter takes 10 applicants on the company's taste job and 3 on a later one; Professional and
above have no limit, and none applies while plan gating is off. The job that takes its last
place is DISABLED in the same transaction, the employer is told, and the next candidate is
turned away. Applications go through the real HTTP flow.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.exceptions import JobNotAcceptingApplications
from app.modules.applications import service as applications_service
from app.modules.applications.models import Application
from app.modules.applications.service import ApplicationService
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.billing import starter_rules
from app.modules.candidates.models import CandidateProfile
from app.modules.jobs.enums import JobStatus
from app.modules.jobs.models import Job
from app.modules.notifications.models import Notification
from app.modules.users.models import Organization, User
from tests.applications import test_applications_router as base
from tests.conftest import (
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
    test_engine,
)
from tests.interviews.conftest import make_candidate_profile, make_candidate_user

# The storage override and the Celery patches the router tests use for every test.
override_storage = base.override_storage
mock_celery_task = base.mock_celery_task


@pytest.fixture(autouse=True)
def gates_on(monkeypatch):
    monkeypatch.setattr(settings, "plan_gates_enabled", True)


async def _company_with_job(db_session, *, taste=False, kyc="APPROVED", plan=None):
    """A company with one live job. ``taste`` makes that job the company's taste job; otherwise
    an older closed job holds the taste and this one is a later job."""
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(
        db_session, employer, company_name="Acme", is_profile_complete=True, kyc_status=kyc
    )
    if plan:
        await make_subscription_for(db_session, organization, plan_code=plan)
    job = make_job(
        employer.id,
        status=JobStatus.ACTIVE.value,
        moderation_status="APPROVED",
        published_at=datetime.now(UTC),
    )
    db_session.add(job)
    await db_session.flush()
    if taste:
        organization.taste_job_id = job.id
    else:
        first = make_job(
            employer.id,
            title="First job",
            status=JobStatus.CLOSED.value,
            moderation_status="APPROVED",
            published_at=datetime.now(UTC) - timedelta(days=60),
        )
        db_session.add(first)
        await db_session.flush()
        organization.taste_job_id = first.id
    await db_session.flush()
    return employer, organization, job


async def _candidate_headers(db_session):
    user = make_candidate_user()
    db_session.add(user)
    await db_session.flush()
    await make_candidate_profile(db_session, user, is_profile_complete=True)
    token = create_token_pair(user.id, "CANDIDATE")["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _apply(client, headers, job):
    return await client.post("/api/v1/applications", json={"job_id": str(job.id)}, headers=headers)


async def _status_of(db_session, job):
    await db_session.refresh(job)
    return job.status, job.disabled_reason


# --- the limits ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_later_starter_job_takes_three_applicants_then_switches_off(client, db_session):
    employer, _org, job = await _company_with_job(db_session)

    for _ in range(3):
        assert (await _apply(client, await _candidate_headers(db_session), job)).status_code == 201

    assert await _status_of(db_session, job) == ("DISABLED", "APPLICANT_LIMIT")
    refused = await _apply(client, await _candidate_headers(db_session), job)
    assert refused.status_code == 422
    assert refused.json()["code"] == "JOB_NOT_ACCEPTING_APPLICATIONS"


@pytest.mark.asyncio
async def test_the_employer_is_told_when_the_job_switches_off(client, db_session):
    employer, _org, job = await _company_with_job(db_session)
    for _ in range(3):
        await _apply(client, await _candidate_headers(db_session), job)

    told = (
        await db_session.execute(
            select(Notification).where(
                Notification.recipient_id == employer.id, Notification.type == "JOB_DISABLED"
            )
        )
    ).scalars().all()

    assert len(told) == 1
    assert "applicant limit" in told[0].title
    assert "re-publish" in told[0].body


@pytest.mark.asyncio
async def test_the_taste_job_takes_more_applicants_than_a_later_one(client, db_session, monkeypatch):
    # The real number is 10 (checked in test_starter_rules); 2 keeps this test quick.
    monkeypatch.setattr(starter_rules, "TASTE_APPLICANT_LIMIT", 2)
    _employer, _org, job = await _company_with_job(db_session, taste=True)

    assert (await _apply(client, await _candidate_headers(db_session), job)).status_code == 201
    assert await _status_of(db_session, job) == ("ACTIVE", None)  # one place left
    assert (await _apply(client, await _candidate_headers(db_session), job)).status_code == 201
    assert await _status_of(db_session, job) == ("DISABLED", "APPLICANT_LIMIT")


@pytest.mark.asyncio
async def test_an_unverified_company_gets_the_smaller_limit_on_its_first_job(client, db_session):
    _employer, _org, job = await _company_with_job(db_session, taste=True, kyc="PENDING")

    for _ in range(3):
        await _apply(client, await _candidate_headers(db_session), job)

    assert await _status_of(db_session, job) == ("DISABLED", "APPLICANT_LIMIT")


@pytest.mark.asyncio
async def test_a_professional_job_has_no_applicant_limit(client, db_session):
    _employer, _org, job = await _company_with_job(db_session, plan="professional")

    for _ in range(4):
        assert (await _apply(client, await _candidate_headers(db_session), job)).status_code == 201

    assert await _status_of(db_session, job) == ("ACTIVE", None)


@pytest.mark.asyncio
async def test_no_limit_while_plan_gating_is_off(client, db_session, monkeypatch):
    """Production today: gating is off, so a Starter job takes any number of applicants."""
    monkeypatch.setattr(settings, "plan_gates_enabled", False)
    _employer, _org, job = await _company_with_job(db_session)

    for _ in range(4):
        assert (await _apply(client, await _candidate_headers(db_session), job)).status_code == 201

    assert await _status_of(db_session, job) == ("ACTIVE", None)


@pytest.mark.asyncio
async def test_a_job_switched_off_for_another_reason_takes_no_applications(client, db_session):
    _employer, _org, job = await _company_with_job(db_session, plan="professional")
    job.status = JobStatus.DISABLED.value
    job.disabled_reason = "EXPIRED"
    await db_session.flush()

    refused = await _apply(client, await _candidate_headers(db_session), job)

    assert refused.status_code == 422
    assert refused.json()["code"] == "JOB_NOT_ACCEPTING_APPLICATIONS"


@pytest.mark.asyncio
async def test_a_candidate_who_already_applied_is_told_so_not_that_the_job_is_off(
    client, db_session
):
    _employer, _org, job = await _company_with_job(db_session)
    headers = await _candidate_headers(db_session)
    assert (await _apply(client, headers, job)).status_code == 201

    again = await _apply(client, headers, job)

    assert again.json()["code"] != "JOB_NOT_ACCEPTING_APPLICATIONS"
    assert again.status_code in (409, 422)


# --- two at the same moment ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_candidates_applying_for_the_last_place_at_once_only_one_gets_it(monkeypatch):
    """Real, separate database sessions and real commits. With the job row locked, the second
    sees the job switched off by the first. (Everything it creates is deleted again.)"""
    monkeypatch.setattr(starter_rules, "LATER_APPLICANT_LIMIT", 1)
    monkeypatch.setattr(applications_service.score_application_task, "delay", MagicMock())
    monkeypatch.setattr(applications_service.compute_match_score_task, "delay", MagicMock())
    RealSession = async_sessionmaker(test_engine, expire_on_commit=False)
    ids = {"users": [], "org": None, "jobs": []}
    try:
        async with RealSession() as setup:
            employer = make_employer()
            setup.add(employer)
            await setup.flush()
            organization = await make_organization_for(
                setup, employer, company_name="Race Ltd", is_profile_complete=True, kyc_status="APPROVED"
            )
            first = make_job(
                employer.id,
                title="First",
                status=JobStatus.CLOSED.value,
                published_at=datetime.now(UTC) - timedelta(days=60),
            )
            job = make_job(employer.id, status=JobStatus.ACTIVE.value, published_at=datetime.now(UTC))
            setup.add_all([first, job])
            await setup.flush()
            organization.taste_job_id = first.id
            candidates = []
            for _ in range(2):
                user = make_candidate_user()
                setup.add(user)
                await setup.flush()
                await make_candidate_profile(setup, user, is_profile_complete=True)
                candidates.append(user.id)
            await setup.commit()
            ids.update(
                users=[employer.id, *candidates], org=organization.id, jobs=[job.id, first.id]
            )
            job_id = job.id

        async def apply(candidate_id):
            async with RealSession() as session:
                try:
                    await ApplicationService(session).apply_to_job(
                        candidate_id, job_id, BackgroundTasks()
                    )
                    return "applied"
                except JobNotAcceptingApplications:
                    return "turned away"

        outcomes = await asyncio.gather(apply(candidates[0]), apply(candidates[1]))

        assert sorted(outcomes) == ["applied", "turned away"]
        async with RealSession() as check:
            count = (
                await check.execute(
                    select(func.count()).select_from(Application).where(Application.job_id == job_id)
                )
            ).scalar_one()
            status = (await check.execute(select(Job.status).where(Job.id == job_id))).scalar_one()
        assert count == 1
        assert status == "DISABLED"
    finally:
        async with RealSession() as cleanup:
            if ids["jobs"]:
                await cleanup.execute(delete(Application).where(Application.job_id.in_(ids["jobs"])))
                await cleanup.execute(
                    delete(Notification).where(Notification.recipient_id.in_(ids["users"]))
                )
            if ids["org"]:
                org = await cleanup.get(Organization, ids["org"])
                if org is not None:
                    org.taste_job_id = None
                await cleanup.flush()
            if ids["jobs"]:
                await cleanup.execute(delete(Job).where(Job.id.in_(ids["jobs"])))
            if ids["users"]:
                await cleanup.execute(
                    delete(CandidateProfile).where(CandidateProfile.user_id.in_(ids["users"]))
                )
                await cleanup.execute(delete(User).where(User.id.in_(ids["users"])))
            if ids["org"]:
                await cleanup.execute(delete(Organization).where(Organization.id == ids["org"]))
            await cleanup.commit()
