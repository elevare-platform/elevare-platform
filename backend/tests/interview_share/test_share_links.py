"""The shared interview results link: making it, revoking it, who may, and who may open it."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.modules.interview_share.models import InterviewShareLink
from app.modules.interview_share.service import SHARE_LINK_DAYS, InterviewShareService
from tests.conftest import make_employer, make_job, make_organization_for
from tests.interviews.test_interview_router import register_and_promote

PUBLIC = "/api/v1/public/interview-results"
OWNER = "/api/v1/interview-share/jobs"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def employer_with_job(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    await make_organization_for(db_session, employer)
    job = make_job(employer.id, interview_brief="Probe distributor management.")
    db_session.add(job)
    await db_session.flush()
    return employer, job


async def active_links(db_session, job_id) -> list[InterviewShareLink]:
    return list(
        (
            await db_session.execute(
                select(InterviewShareLink).where(
                    InterviewShareLink.job_id == job_id,
                    InterviewShareLink.revoked_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )


def token_of(url: str) -> str:
    return url.rsplit("/", 1)[1]


# --- making the link -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_link_opens_for_three_days_and_is_a_page_on_the_website(db_session):
    employer, job = await employer_with_job(db_session)

    link = await InterviewShareService(db_session).create(employer, job.id)

    assert SHARE_LINK_DAYS == 3
    assert "/shared/interviews/" in link.url
    remaining = link.expires_at - datetime.now(UTC)
    assert timedelta(days=3) - timedelta(minutes=1) < remaining <= timedelta(days=3)
    assert (link.expired, link.view_count, link.last_viewed_at) == (False, 0, None)


@pytest.mark.asyncio
async def test_a_job_with_no_link_says_so(db_session):
    employer, job = await employer_with_job(db_session)

    status = await InterviewShareService(db_session).get_status(employer, job.id)

    assert status.link is None


@pytest.mark.asyncio
async def test_making_a_new_link_replaces_the_old_one(db_session):
    employer, job = await employer_with_job(db_session)
    service = InterviewShareService(db_session)
    first = await service.create(employer, job.id)

    second = await service.create(employer, job.id)

    assert token_of(first.url) != token_of(second.url)
    [only] = await active_links(db_session, job.id)
    assert only.token == token_of(second.url)
    # The old link no longer opens.
    with pytest.raises(Exception) as error:
        await service.get_results(token_of(first.url))
    assert error.value.code == "SHARE_LINK_REVOKED"


@pytest.mark.asyncio
async def test_the_database_allows_only_one_active_link_per_job(db_session):
    """Two people pressing Share at once cannot both end up with a live link."""
    _, job = await employer_with_job(db_session)
    when = datetime.now(UTC) + timedelta(days=3)
    db_session.add(InterviewShareLink(job_id=job.id, token="a" * 20, expires_at=when))
    await db_session.flush()

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(InterviewShareLink(job_id=job.id, token="b" * 20, expires_at=when))
            await db_session.flush()


@pytest.mark.asyncio
async def test_revoking_stops_the_link_and_clears_it_from_the_job(db_session):
    employer, job = await employer_with_job(db_session)
    service = InterviewShareService(db_session)
    link = await service.create(employer, job.id)

    await service.revoke(employer, job.id)

    assert (await service.get_status(employer, job.id)).link is None
    with pytest.raises(Exception) as error:
        await service.get_results(token_of(link.url))
    assert error.value.code == "SHARE_LINK_REVOKED"


@pytest.mark.asyncio
async def test_revoking_when_there_is_no_link_is_harmless(db_session):
    employer, job = await employer_with_job(db_session)

    await InterviewShareService(db_session).revoke(employer, job.id)


@pytest.mark.asyncio
async def test_an_expired_link_is_still_shown_to_its_owner_as_expired(db_session):
    employer, job = await employer_with_job(db_session)
    service = InterviewShareService(db_session)
    await service.create(employer, job.id)
    [link] = await active_links(db_session, job.id)
    link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    status = await service.get_status(employer, job.id)

    assert status.link.expired is True


# --- who may make it -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_someone_in_the_same_organization_may_make_the_link(client, db_session):
    token, owner = await register_and_promote(client, db_session, "EMPLOYER")
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()

    resp = await client.post(f"{OWNER}/{job.id}", headers=auth(token))

    assert resp.status_code == 201
    assert "/shared/interviews/" in resp.json()["url"]


@pytest.mark.asyncio
async def test_an_employer_from_another_organization_may_not(client, db_session):
    _, owner = await register_and_promote(client, db_session, "EMPLOYER")
    other_token, _ = await register_and_promote(client, db_session, "EMPLOYER")
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()

    for method in ("get", "post", "delete"):
        resp = await getattr(client, method)(f"{OWNER}/{job.id}", headers=auth(other_token))
        assert resp.status_code == 403, method
    assert await active_links(db_session, job.id) == []


@pytest.mark.asyncio
async def test_an_elevare_admin_may_make_the_link_for_a_clients_job(client, db_session):
    """Elevare staff run the interviews for a client, so they share the results."""
    _, owner = await register_and_promote(client, db_session, "EMPLOYER")
    admin_token, _ = await register_and_promote(client, db_session, "ADMIN")
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()

    resp = await client.post(f"{OWNER}/{job.id}", headers=auth(admin_token))

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_a_candidate_may_not(client, db_session):
    _, owner = await register_and_promote(client, db_session, "EMPLOYER")
    candidate_token, _ = await register_and_promote(client, db_session, "CANDIDATE")
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()

    assert (await client.post(f"{OWNER}/{job.id}", headers=auth(candidate_token))).status_code == 403


@pytest.mark.asyncio
async def test_making_a_link_needs_a_login(client, db_session):
    _, job = await employer_with_job(db_session)

    assert (await client.post(f"{OWNER}/{job.id}")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_a_job_that_does_not_exist_is_not_found(client, db_session):
    import uuid

    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    resp = await client.post(f"{OWNER}/{uuid.uuid4()}", headers=auth(token))

    assert resp.status_code == 404


# --- opening it (no login) -------------------------------------------------------------


@pytest.fixture
def storage(monkeypatch):
    """The recording's signed link, without touching real storage."""
    from app.modules.interviews import service as interview_service_module

    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/video")
    monkeypatch.setattr(interview_service_module, "get_storage_service", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_the_link_opens_with_no_login_and_is_never_cached(client, db_session, storage):
    employer, job = await employer_with_job(db_session)
    link = await InterviewShareService(db_session).create(employer, job.id)

    resp = await client.get(f"{PUBLIC}/{token_of(link.url)}")

    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert body["job_title"] == job.title
    assert body["interview_focus"] == "Probe distributor management."


@pytest.mark.asyncio
async def test_opening_the_link_is_counted(client, db_session, storage):
    employer, job = await employer_with_job(db_session)
    service = InterviewShareService(db_session)
    link = await service.create(employer, job.id)

    await client.get(f"{PUBLIC}/{token_of(link.url)}")
    await client.get(f"{PUBLIC}/{token_of(link.url)}")

    status = await service.get_status(employer, job.id)
    assert status.link.view_count == 2
    assert status.link.last_viewed_at is not None


@pytest.mark.asyncio
async def test_a_link_that_does_not_exist_is_not_found(client):
    resp = await client.get(f"{PUBLIC}/not-a-real-token")

    assert resp.status_code == 404
    assert resp.json()["code"] == "SHARE_LINK_NOT_FOUND"


@pytest.mark.asyncio
async def test_a_replaced_or_revoked_link_says_so(client, db_session):
    employer, job = await employer_with_job(db_session)
    service = InterviewShareService(db_session)
    link = await service.create(employer, job.id)
    await service.revoke(employer, job.id)

    resp = await client.get(f"{PUBLIC}/{token_of(link.url)}")

    assert resp.status_code == 410
    assert resp.json()["code"] == "SHARE_LINK_REVOKED"


@pytest.mark.asyncio
async def test_an_expired_link_says_so_and_is_not_counted_as_a_view(client, db_session):
    employer, job = await employer_with_job(db_session)
    service = InterviewShareService(db_session)
    link = await service.create(employer, job.id)
    [row] = await active_links(db_session, job.id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    resp = await client.get(f"{PUBLIC}/{token_of(link.url)}")

    assert resp.status_code == 410
    assert resp.json()["code"] == "SHARE_LINK_EXPIRED"
    assert row.view_count == 0
