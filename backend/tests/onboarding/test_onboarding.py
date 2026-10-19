"""The first-login tour and checklist progress endpoints."""

import pytest
from sqlalchemy import func, select

from app.modules.onboarding.models import CHECKLIST_STEPS, UserOnboarding
from tests.interviews.test_interview_router import register_and_promote

BASE = "/api/v1/onboarding/me"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def row_count(db_session, user_id) -> int:
    return (
        await db_session.execute(
            select(func.count())
            .select_from(UserOnboarding)
            .where(UserOnboarding.user_id == user_id)
        )
    ).scalar_one()


@pytest.mark.asyncio
async def test_a_new_employer_has_not_seen_the_tour_and_reading_stores_nothing(
    client, db_session
):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    first = await client.get(BASE, headers=auth(token))
    second = await client.get(BASE, headers=auth(token))

    assert first.status_code == 200
    assert first.json() == {
        "tour_status": "PENDING",
        "completed_steps": [],
        "checklist_dismissed": False,
    }
    assert second.json() == first.json()
    assert await row_count(db_session, user.id) == 0


@pytest.mark.asyncio
async def test_finishing_the_tour_is_remembered(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    done = await client.post(BASE + "/tour", json={"outcome": "COMPLETED"}, headers=auth(token))

    assert done.status_code == 200
    assert done.json()["tour_status"] == "COMPLETED"
    assert (await client.get(BASE, headers=auth(token))).json()["tour_status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_skipping_is_remembered_too(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    await client.post(BASE + "/tour", json={"outcome": "SKIPPED"}, headers=auth(token))

    assert (await client.get(BASE, headers=auth(token))).json()["tour_status"] == "SKIPPED"


@pytest.mark.asyncio
async def test_closing_a_replay_early_does_not_undo_a_completed_tour(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")
    await client.post(BASE + "/tour", json={"outcome": "COMPLETED"}, headers=auth(token))

    again = await client.post(BASE + "/tour", json={"outcome": "SKIPPED"}, headers=auth(token))

    assert again.json()["tour_status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_a_step_is_recorded_once_however_often_it_is_reported(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    for _ in range(3):
        response = await client.post(
            BASE + "/steps", json={"step": "talent_pool"}, headers=auth(token)
        )

    assert response.status_code == 200
    assert response.json()["completed_steps"] == ["talent_pool"]
    assert await row_count(db_session, user.id) == 1


@pytest.mark.asyncio
async def test_different_steps_add_up_and_leave_the_tour_status_alone(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    await client.post(BASE + "/steps", json={"step": "talent_pool"}, headers=auth(token))
    response = await client.post(BASE + "/steps", json={"step": "credits"}, headers=auth(token))

    body = response.json()
    assert sorted(body["completed_steps"]) == ["credits", "talent_pool"]
    assert body["tour_status"] == "PENDING"


@pytest.mark.asyncio
async def test_every_checklist_step_the_server_knows_is_accepted(client, db_session):
    token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    for step in CHECKLIST_STEPS:
        response = await client.post(BASE + "/steps", json={"step": step}, headers=auth(token))
        assert response.status_code == 200, step

    assert sorted(response.json()["completed_steps"]) == sorted(CHECKLIST_STEPS)


@pytest.mark.asyncio
async def test_an_unknown_step_or_outcome_is_rejected(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    bad_step = await client.post(BASE + "/steps", json={"step": "drop table"}, headers=auth(token))
    bad_outcome = await client.post(BASE + "/tour", json={"outcome": "PENDING"}, headers=auth(token))

    assert bad_step.status_code == 422
    assert bad_outcome.status_code == 422
    assert await row_count(db_session, user.id) == 0


@pytest.mark.asyncio
async def test_dismissing_the_checklist_is_remembered_and_repeatable(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")

    first = await client.post(BASE + "/checklist/dismiss", headers=auth(token))
    second = await client.post(BASE + "/checklist/dismiss", headers=auth(token))

    assert first.json()["checklist_dismissed"] is True
    assert second.json()["checklist_dismissed"] is True
    assert await row_count(db_session, user.id) == 1


@pytest.mark.asyncio
async def test_each_person_has_their_own_progress(client, db_session):
    first_token, _ = await register_and_promote(client, db_session, "EMPLOYER")
    second_token, _ = await register_and_promote(client, db_session, "EMPLOYER")

    await client.post(BASE + "/tour", json={"outcome": "COMPLETED"}, headers=auth(first_token))
    await client.post(BASE + "/steps", json={"step": "credits"}, headers=auth(first_token))

    other = (await client.get(BASE, headers=auth(second_token))).json()
    assert other == {
        "tour_status": "PENDING",
        "completed_steps": [],
        "checklist_dismissed": False,
    }


@pytest.mark.asyncio
async def test_a_step_that_was_later_retired_is_not_sent_to_the_app(client, db_session):
    token, user = await register_and_promote(client, db_session, "EMPLOYER")
    db_session.add(UserOnboarding(user_id=user.id, completed_steps=["talent_pool", "old_step"]))
    await db_session.flush()

    body = (await client.get(BASE, headers=auth(token))).json()

    assert body["completed_steps"] == ["talent_pool"]


@pytest.mark.asyncio
async def test_a_candidate_has_a_tour_too(client, db_session):
    token, _ = await register_and_promote(client, db_session, "CANDIDATE")

    first = await client.get(BASE, headers=auth(token))
    done = await client.post(BASE + "/tour", json={"outcome": "SKIPPED"}, headers=auth(token))

    assert first.status_code == 200
    assert first.json()["tour_status"] == "PENDING"
    assert done.json()["tour_status"] == "SKIPPED"
    assert (await client.get(BASE, headers=auth(token))).json()["tour_status"] == "SKIPPED"


@pytest.mark.asyncio
async def test_the_checklist_is_for_employers_only(client, db_session):
    candidate_token, user = await register_and_promote(client, db_session, "CANDIDATE")

    steps = await client.post(
        BASE + "/steps", json={"step": "credits"}, headers=auth(candidate_token)
    )
    dismiss = await client.post(BASE + "/checklist/dismiss", headers=auth(candidate_token))

    assert steps.status_code == 403
    assert dismiss.status_code == 403
    assert await row_count(db_session, user.id) == 0


@pytest.mark.asyncio
async def test_admins_and_signed_out_visitors_are_refused(client, db_session):
    admin_token, _ = await register_and_promote(client, db_session, "ADMIN")

    assert (await client.get(BASE, headers=auth(admin_token))).status_code == 403
    assert (await client.get(BASE)).status_code == 401
