"""An admin creates interview-only draft jobs inside a client's account.

The client has not uploaded company documents, so they cannot post a job
themselves. A draft stays off the public board, and the client writes the AI
interview brief and runs the interviews from it."""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.modules.admin.models import AuditLog
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.credits.service import CreditsService
from app.modules.interviews.service import InterviewService
from app.modules.jobs.models import Job
from tests.conftest import make_admin, make_employer, make_organization_for, make_user
from tests.interviews.conftest import make_talent_pool_profile


@pytest.fixture(autouse=True)
def embedding_task(monkeypatch):
    """Do not queue real work on the local worker; keep the call to assert on."""
    from unittest.mock import Mock

    from app.modules.ai import tasks

    queued = Mock()
    monkeypatch.setattr(tasks.generate_job_embedding_task, "delay", queued)
    return queued


def _url(employer_id) -> str:
    return f"/api/v1/admin/employers/{employer_id}/jobs"


def _body(**overrides):
    body = {
        "title": "National Sales Manager",
        "about_the_role": "Lead national sales for a fast-moving consumer goods brand.",
        "key_responsibilities": "Own the national sales plan and the distributor network.",
        "requirements": "Twelve years of progressive FMCG sales experience.",
        "location": "Lagos, Nigeria",
        "contract_type": "FULL_TIME",
        "work_location": "LOCAL",
    }
    body.update(overrides)
    return body


def _bearer(user) -> dict:
    token = create_token_pair(user.id, user.role)["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _admin(db_session):
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    return admin


async def _unverified_client(db_session):
    """A client with an organization whose company documents were never uploaded."""
    client_user = make_employer()
    db_session.add(client_user)
    await db_session.flush()
    await make_organization_for(
        db_session, client_user, company_name="Colton Group", kyc_status="NOT_SUBMITTED"
    )
    return client_user


async def _create(client, db_session, **overrides):
    admin = await _admin(db_session)
    client_user = await _unverified_client(db_session)
    response = await client.post(
        _url(client_user.id), json=_body(**overrides), headers=_bearer(admin)
    )
    return admin, client_user, response


@pytest.mark.asyncio
async def test_the_job_is_a_draft_owned_by_the_client_not_the_admin(client, db_session):
    admin, client_user, response = await _create(client, db_session)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["title"] == "National Sales Manager"
    assert body["interview_brief"] is None
    job = await db_session.get(Job, body["id"])
    assert job.employer_id == client_user.id
    assert job.employer_id != admin.id
    assert job.moderation_status != "APPROVED"


@pytest.mark.asyncio
async def test_the_job_gets_its_matching_embedding_like_any_new_job(
    client, db_session, embedding_task
):
    """Without one, publishing the job later would find nothing to match with."""
    _admin_user, _client_user, response = await _create(client, db_session)

    embedding_task.assert_called_once_with(response.json()["id"])


@pytest.mark.asyncio
async def test_the_client_sees_it_and_the_public_does_not(client, db_session):
    _admin_user, client_user, response = await _create(client, db_session)
    job_id = response.json()["id"]

    # A draft awaiting approval is listed under the "pending" bucket (the default
    # bucket is "active"), which is where the client will find it.
    mine = await client.get(
        "/api/v1/jobs/mine", params={"filter": "pending"}, headers=_bearer(client_user)
    )
    assert mine.status_code == 200
    assert job_id in [job["id"] for job in mine.json()["items"]]

    public = await client.get(f"/api/v1/jobs/{job_id}")
    assert public.status_code == 404


@pytest.mark.asyncio
async def test_the_client_can_write_the_interview_brief_without_verification(
    client, db_session
):
    _admin_user, client_user, response = await _create(client, db_session)
    job_id = response.json()["id"]

    edited = await client.patch(
        f"/api/v1/jobs/{job_id}",
        json={"interview_brief": "Probe distributor management and route-to-market."},
        headers=_bearer(client_user),
    )

    assert edited.status_code == 200
    assert edited.json()["interview_brief"].startswith("Probe distributor")
    assert edited.json()["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_an_interview_can_be_run_from_the_draft(client, db_session):
    """The point of the whole arrangement: a draft job, owned by a client who has
    no company verification, is enough to interview the candidates sourced for it."""
    _admin_user, client_user, response = await _create(client, db_session)
    job_id = response.json()["id"]
    await client.patch(
        f"/api/v1/jobs/{job_id}",
        json={"interview_brief": "Probe distributor management."},
        headers=_bearer(client_user),
    )
    profile = await make_talent_pool_profile(db_session, added_by_id=client_user.id)
    # An interview costs credits; the client has bought some.
    await CreditsService(db_session).grant(client_user.organization_id, 100)

    service = InterviewService(db_session)
    try:
        link = await service.get_interview_link(client_user, job_id, profile.id)
    finally:
        await service.close()

    assert "/interview/" in link["interview_url"]


@pytest.mark.asyncio
async def test_the_client_cannot_publish_it_without_an_admin_approval(
    client, db_session
):
    _admin_user, client_user, response = await _create(client, db_session)

    published = await client.post(
        f"/api/v1/jobs/{response.json()['id']}/publish", headers=_bearer(client_user)
    )

    assert published.status_code == 422


@pytest.mark.asyncio
async def test_the_admin_cannot_write_the_interview_brief(client, db_session):
    _admin_user, _client_user, response = await _create(
        client, db_session, interview_brief="Probe distributor management."
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_same_title_twice_is_refused(client, db_session):
    admin = await _admin(db_session)
    client_user = await _unverified_client(db_session)

    first = await client.post(
        _url(client_user.id), json=_body(), headers=_bearer(admin)
    )
    second = await client.post(
        _url(client_user.id),
        json=_body(title="national sales manager"),
        headers=_bearer(admin),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    jobs = (
        (await db_session.execute(select(Job).where(Job.employer_id == client_user.id)))
        .scalars()
        .all()
    )
    assert len(jobs) == 1


@pytest.mark.asyncio
async def test_an_audit_entry_records_who_created_which_job(client, db_session):
    admin, client_user, response = await _create(client, db_session)

    # Only this job's entry: the dev database may hold others from real use.
    entry = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "CREATE_CLIENT_JOB",
                AuditLog.target_id == UUID(response.json()["id"]),
            )
        )
    ).scalar_one()
    assert entry.admin_id == admin.id
    assert entry.log_metadata["employer_id"] == str(client_user.id)
    assert entry.log_metadata["title"] == "National Sales Manager"


@pytest.mark.asyncio
async def test_an_unknown_employer_is_a_404(client, db_session):
    from uuid import uuid4

    admin = await _admin(db_session)

    response = await client.post(_url(uuid4()), json=_body(), headers=_bearer(admin))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_job_cannot_be_created_for_someone_who_is_not_an_employer(
    client, db_session
):
    admin = await _admin(db_session)
    candidate = make_user(role="CANDIDATE")
    db_session.add(candidate)
    await db_session.flush()

    response = await client.post(
        _url(candidate.id), json=_body(), headers=_bearer(admin)
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [{"title": "ab"}, {"about_the_role": "short"}, {"contract_type": "NOT_A_TYPE"}],
)
async def test_the_usual_job_validation_applies(client, db_session, overrides):
    _admin_user, _client_user, response = await _create(client, db_session, **overrides)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_only_an_admin_can_create_a_job_for_a_client(client, db_session):
    client_user = await _unverified_client(db_session)
    other_employer = make_employer()
    db_session.add(other_employer)
    await db_session.flush()

    refused = await client.post(
        _url(client_user.id), json=_body(), headers=_bearer(other_employer)
    )
    anonymous = await client.post(_url(client_user.id), json=_body())

    assert refused.status_code == 403
    assert anonymous.status_code == 401
