"""Sending a job's AI interview to a typed email address, with no CV and no account.

The address gets a pool row of its own so the interview works like any other, goes on the job's
interview list and stays there, and never shows in the Talent Pool page."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.interview_list.models import InterviewListEntry
from app.modules.interviews import service as service_module
from app.modules.interviews.models import Interview, JobInterviewQuestion
from app.modules.talent_pool.models import TalentPoolProfiles
from tests.conftest import make_employer, make_job

from .conftest import make_candidate_profile, make_candidate_user

BRIEF = "Find out how they design systems."


def headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


def url(job):
    return f"/api/v1/interviews/jobs/{job.id}/invite-by-email"


@pytest.fixture
def invite_email(monkeypatch):
    task = MagicMock()
    monkeypatch.setattr(service_module, "send_ai_interview_invite_email", task)
    return task


async def company(db_session, brief=BRIEF):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id, interview_brief=brief)
    db_session.add(job)
    await db_session.flush()
    return employer, job


async def invite(client, employer, job, email="ada@example.com"):
    return await client.post(url(job), json={"email": email}, headers=headers(employer))


async def pool_rows(db_session, email):
    result = await db_session.execute(
        select(TalentPoolProfiles).where(TalentPoolProfiles.override_email == email)
    )
    return list(result.scalars().all())


async def entries(db_session, job):
    result = await db_session.execute(select(InterviewListEntry).where(InterviewListEntry.job_id == job.id))
    return list(result.scalars().all())


# --- what it does ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_it_emails_the_link_puts_the_address_on_the_interview_list_and_makes_the_interview(
    client, db_session, invite_email
):
    employer, job = await company(db_session)

    resp = await invite(client, employer, job, "Ada@Example.com ")

    assert resp.status_code == 200
    body = resp.json()
    assert body["sent"] is True and body["reason"] is None
    [row] = await pool_rows(db_session, "ada@example.com")  # stored in lower case, trimmed
    assert row.source == "interview_invite" and row.added_by == employer.id
    assert row.parsed_submission_id is None and row.candidate_profile_id is None
    assert str(row.id) == body["talent_pool_profile_id"]
    [entry] = await entries(db_session, job)
    assert entry.employer_id == employer.id and entry.talent_pool_profile_id == row.id
    interview = (await db_session.execute(select(Interview).where(Interview.job_id == job.id))).scalar_one()
    assert interview.status == "PENDING" and interview.talent_pool_profile_id == row.id
    kwargs = invite_email.delay.call_args.kwargs
    assert kwargs["candidate_email"] == "ada@example.com"
    assert kwargs["interview_url"].endswith(interview.token)
    assert kwargs["job_title"] == job.title


@pytest.mark.asyncio
async def test_the_address_shows_on_the_interview_list_with_its_status_and_nothing_to_open(
    client, db_session, invite_email
):
    employer, job = await company(db_session)
    await invite(client, employer, job)

    listed = (
        await client.get("/api/v1/interview-list", params={"job_id": str(job.id)}, headers=headers(employer))
    ).json()

    [item] = listed["items"]
    assert item["candidate_name"] == "ada@example.com"
    assert item["email_only"] is True
    assert item["interview_status"] == "PENDING"


@pytest.mark.asyncio
async def test_typing_the_same_address_again_resends_and_never_makes_a_second_row(
    client, db_session, invite_email
):
    employer, job = await company(db_session)

    first = (await invite(client, employer, job, "ada@example.com")).json()
    second = (await invite(client, employer, job, "ADA@example.com")).json()

    assert first["talent_pool_profile_id"] == second["talent_pool_profile_id"]
    assert len(await pool_rows(db_session, "ada@example.com")) == 1
    assert len(await entries(db_session, job)) == 1
    assert invite_email.delay.call_count == 2
    interviews = (await db_session.execute(select(Interview).where(Interview.job_id == job.id))).scalars().all()
    assert len(interviews) == 1


@pytest.mark.asyncio
async def test_an_address_that_belongs_to_a_registered_candidate_uses_their_own_profile(
    client, db_session, invite_email
):
    employer, job = await company(db_session)
    user = make_candidate_user(email="grace@example.com")
    db_session.add(user)
    await db_session.flush()
    profile = await make_candidate_profile(db_session, user)
    pool = TalentPoolProfiles(added_by=user.id, candidate_profile_id=profile.id, source="OTHER")
    db_session.add(pool)
    await db_session.flush()

    resp = await invite(client, employer, job, "grace@example.com")

    assert resp.status_code == 200 and resp.json()["talent_pool_profile_id"] == str(pool.id)
    assert await pool_rows(db_session, "grace@example.com") == []  # no extra row
    [entry] = await entries(db_session, job)
    assert entry.talent_pool_profile_id == pool.id


@pytest.mark.asyncio
async def test_a_failed_send_keeps_the_address_on_the_list_so_it_can_be_sent_again(
    client, db_session, invite_email, monkeypatch
):
    employer, job = await company(db_session)
    monkeypatch.setattr(
        service_module.InterviewService,
        "_send_invite_for_profile",
        AsyncMock(return_value={"sent": False, "reason": "Not enough credits"}),
    )

    resp = await invite(client, employer, job)

    assert resp.status_code == 200
    assert resp.json()["sent"] is False and resp.json()["reason"] == "Not enough credits"
    assert len(await entries(db_session, job)) == 1
    assert len(await pool_rows(db_session, "ada@example.com")) == 1


@pytest.mark.asyncio
async def test_a_strict_job_with_no_questions_says_so_and_keeps_the_address(
    client, db_session, invite_email, monkeypatch
):
    monkeypatch.setattr(settings, "interview_style", "strict")
    employer, job = await company(db_session)

    resp = await invite(client, employer, job)

    assert resp.status_code == 200 and resp.json()["sent"] is False
    assert "questions" in resp.json()["reason"].lower()
    assert len(await entries(db_session, job)) == 1
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_a_strict_job_with_questions_sends_a_strict_invite(client, db_session, invite_email, monkeypatch):
    monkeypatch.setattr(settings, "interview_style", "strict")
    employer, job = await company(db_session)
    db_session.add(
        JobInterviewQuestion(
            job_id=job.id, position=1, text="Describe a system you built.", time_limit_seconds=120, source="EMPLOYER"
        )
    )
    await db_session.flush()

    resp = await invite(client, employer, job)

    assert resp.json()["sent"] is True
    assert invite_email.delay.call_args.kwargs["strict"] is True


# --- who may, and what is refused ------------------------------------------------------------


@pytest.mark.asyncio
async def test_another_company_cannot_invite_for_this_job(client, db_session, invite_email):
    _owner, job = await company(db_session)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.flush()

    resp = await invite(client, stranger, job)

    assert resp.status_code == 403
    assert await pool_rows(db_session, "ada@example.com") == []
    invite_email.delay.assert_not_called()


@pytest.mark.asyncio
async def test_a_candidate_cannot_use_it_and_an_anonymous_call_is_refused(client, db_session):
    _employer, job = await company(db_session)
    candidate = make_candidate_user()
    db_session.add(candidate)
    await db_session.flush()

    assert (await invite(client, candidate, job)).status_code == 403
    assert (await client.post(url(job), json={"email": "ada@example.com"})).status_code == 401


@pytest.mark.asyncio
async def test_a_job_without_an_interview_set_up_is_refused_and_leaves_nothing_behind(
    client, db_session, invite_email
):
    employer, job = await company(db_session, brief=None)

    resp = await invite(client, employer, job)

    assert resp.status_code == 422
    assert await pool_rows(db_session, "ada@example.com") == []
    assert await entries(db_session, job) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["", "not an email", "a@", "@b.com", "a b@c.com"])
async def test_a_bad_address_is_refused(client, db_session, invite_email, bad):
    employer, job = await company(db_session)

    resp = await invite(client, employer, job, bad)

    assert resp.status_code == 422
    assert await entries(db_session, job) == []


@pytest.mark.asyncio
async def test_it_is_refused_while_interviews_are_switched_off(client, db_session, invite_email, monkeypatch):
    monkeypatch.setattr(settings, "interview_enabled", False)
    employer, job = await company(db_session)

    resp = await invite(client, employer, job)

    assert resp.status_code == 503 and resp.json()["code"] == "AI_INTERVIEWS_DISABLED"
    assert await pool_rows(db_session, "ada@example.com") == []


@pytest.mark.asyncio
async def test_an_unknown_job_is_a_404(client, db_session):
    employer, _job = await company(db_session)

    resp = await client.post(
        f"/api/v1/interviews/jobs/{uuid.uuid4()}/invite-by-email",
        json={"email": "ada@example.com"},
        headers=headers(employer),
    )

    assert resp.status_code == 404


# --- where it must not show up -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_address_does_not_appear_in_the_talent_pool_page(client, db_session, invite_email):
    employer, job = await company(db_session)
    await invite(client, employer, job)

    pool = (await client.get("/api/v1/talent-pool", headers=headers(employer))).json()

    assert pool["items"] == []
