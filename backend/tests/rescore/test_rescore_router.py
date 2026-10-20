"""The rescore endpoints over HTTP: who may call them and what they answer."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.modules.ai import tasks as ai_tasks
from app.modules.ai.scoring_outcome import SCORING_FAILED
from app.modules.users.models import Organization
from tests.conftest import make_job, make_subscription_for
from tests.interviews.test_interview_router import register_and_promote
from tests.rescore.test_rescore import application_for

BASE = "/api/v1/rescore/jobs"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def nothing_runs(monkeypatch):
    monkeypatch.setattr(ai_tasks.score_application_task, "delay", MagicMock())
    monkeypatch.setattr(ai_tasks.score_talent_pool_profile_task, "delay", MagicMock())
    monkeypatch.setattr(ai_tasks.run_full_pipeline_task, "delay", MagicMock())


async def signed_in_employer_with_job(client, db_session, professional=True):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    if professional:
        organization = (
            await db_session.execute(select(Organization).where(Organization.id == user.organization_id))
        ).scalar_one()
        await make_subscription_for(db_session, organization)
    job = make_job(user.id)
    db_session.add(job)
    await db_session.flush()
    return token, user, job


@pytest.mark.asyncio
async def test_status_and_rescore_answer_with_counts(client, db_session):
    token, _, job = await signed_in_employer_with_job(client, db_session)
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    status = await client.get(f"{BASE}/{job.id}", headers=auth(token))
    assert status.status_code == 200
    assert status.json() == {"applications": 1, "pipeline": 0, "total": 1}

    done = await client.post(f"{BASE}/{job.id}", headers=auth(token))
    assert done.status_code == 200
    assert done.json() == {
        "scoring": 1,
        "reparsing": 0,
        "in_progress": 0,
        "no_stored_file": 0,
        "remaining": 0,
    }


@pytest.mark.asyncio
async def test_one_candidate_can_be_named_in_the_body(client, db_session):
    token, _, job = await signed_in_employer_with_job(client, db_session)
    chosen = await application_for(db_session, job, ai_score_failure=SCORING_FAILED)
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    done = await client.post(
        f"{BASE}/{job.id}", json={"application_id": str(chosen.id)}, headers=auth(token)
    )

    assert done.status_code == 200
    assert done.json()["scoring"] == 1
    assert (await client.get(f"{BASE}/{job.id}", headers=auth(token))).json()["total"] == 1


@pytest.mark.asyncio
async def test_naming_both_kinds_at_once_is_refused(client, db_session):
    token, _, job = await signed_in_employer_with_job(client, db_session)
    one = "00000000-0000-0000-0000-000000000001"

    response = await client.post(
        f"{BASE}/{job.id}",
        json={"application_id": one, "talent_pool_profile_id": one},
        headers=auth(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_the_starter_plan_gets_the_upgrade_error(client, db_session):
    token, _, job = await signed_in_employer_with_job(client, db_session, professional=False)
    await application_for(db_session, job, ai_score_failure=SCORING_FAILED)

    response = await client.post(f"{BASE}/{job.id}", headers=auth(token))

    assert response.status_code == 403
    assert response.json()["code"] == "PLAN_UPGRADE_REQUIRED"
    # Looking is free: only the model calls are a paid feature.
    assert (await client.get(f"{BASE}/{job.id}", headers=auth(token))).status_code == 200


@pytest.mark.asyncio
async def test_someone_else_s_job_is_refused(client, db_session):
    _, _, job = await signed_in_employer_with_job(client, db_session)
    outsider_token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    assert (await client.get(f"{BASE}/{job.id}", headers=auth(outsider_token))).status_code == 403
    assert (await client.post(f"{BASE}/{job.id}", headers=auth(outsider_token))).status_code == 403


@pytest.mark.asyncio
async def test_an_unknown_job_is_not_found(client, db_session):
    token, _, _ = await signed_in_employer_with_job(client, db_session)

    response = await client.post(
        f"{BASE}/00000000-0000-0000-0000-00000000dead", headers=auth(token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_candidates_and_signed_out_visitors_are_refused(client, db_session):
    _, _, job = await signed_in_employer_with_job(client, db_session)
    candidate_token, _ = await register_and_promote(client, db_session, "CANDIDATE")

    assert (await client.get(f"{BASE}/{job.id}", headers=auth(candidate_token))).status_code == 403
    assert (await client.post(f"{BASE}/{job.id}", headers=auth(candidate_token))).status_code == 403
    assert (await client.get(f"{BASE}/{job.id}")).status_code == 401
    assert (await client.post(f"{BASE}/{job.id}")).status_code == 401
