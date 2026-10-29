"""An Elevare admin can open any account's interview list and interview (to review a score).

Before this the interview list was keyed to the person who added each candidate and the detail to the
job's own company, so an admin could not reach the Colton account's interviews from the admin pages.
Everyone else's access is unchanged."""

import pytest

from tests.conftest import make_employer, make_organization_for

from .conftest import make_interview_list_entry, make_talent_pool_profile
from .test_score_review import an_admin, detail, headers, review_url, scored_at


def list_url(interview):
    return f"/api/v1/interview-list?job_id={interview.job.id}"


async def teammate_entry(db_session, interview, name_hint="Second"):
    """A second candidate on the same job's interview list, added by a teammate of the owner."""
    organization = await make_organization_for(db_session, interview.employer, company_name="Acme")
    teammate = make_employer(organization_id=organization.id)
    db_session.add(teammate)
    await db_session.flush()
    profile = await make_talent_pool_profile(db_session, added_by_id=teammate.id)
    await make_interview_list_entry(db_session, teammate.id, profile.id, interview.job.id)
    await db_session.commit()
    return teammate, profile


@pytest.mark.asyncio
async def test_an_admin_sees_every_entry_on_another_accounts_job_whoever_added_it(client, db_session):
    interview = await scored_at(db_session, 58)
    teammate, profile = await teammate_entry(db_session, interview)
    admin = await an_admin(db_session)
    await db_session.commit()

    as_admin = (await client.get(list_url(interview), headers=headers(admin))).json()
    as_owner = (await client.get(list_url(interview), headers=headers(interview.employer))).json()
    as_teammate = (await client.get(list_url(interview), headers=headers(teammate))).json()

    assert as_admin["total"] == 2
    assert {item["talent_pool_profile_id"] for item in as_admin["items"]} == {
        str(interview.interview.talent_pool_profile_id),
        str(profile.id),
    }
    # Unchanged for everyone else: each sees the entries they added.
    assert as_owner["total"] == 1 and as_teammate["total"] == 1


@pytest.mark.asyncio
async def test_a_stranger_still_sees_nothing_of_another_accounts_list(client, db_session):
    interview = await scored_at(db_session, 58)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.commit()

    body = (await client.get(list_url(interview), headers=headers(stranger))).json()

    assert body["total"] == 0


@pytest.mark.asyncio
async def test_an_unknown_job_is_not_found_for_an_admin(client, db_session):
    from uuid import uuid4

    admin = await an_admin(db_session)
    await db_session.commit()

    resp = await client.get(f"/api/v1/interview-list?job_id={uuid4()}", headers=headers(admin))

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_the_admins_list_carries_the_score_shown_and_whether_it_was_reviewed_and_nobody_elses_does(
    client, db_session
):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    before = (await client.get(list_url(interview), headers=headers(admin))).json()["items"][0]
    await client.put(review_url(interview), json={"score": 89}, headers=headers(admin))
    after = (await client.get(list_url(interview), headers=headers(admin))).json()["items"][0]
    owner = (await client.get(list_url(interview), headers=headers(interview.employer))).json()["items"][0]

    assert (before["interview_score"], before["interview_reviewed"]) == (58, False)
    assert (after["interview_score"], after["interview_reviewed"]) == (89, True)
    assert (owner["interview_score"], owner["interview_reviewed"]) == (None, False)


@pytest.mark.asyncio
async def test_an_interview_that_is_not_scored_has_no_score_in_the_admins_list(client, db_session):
    interview = await scored_at(db_session, 58)
    interview.interview.status = "UPLOADED"
    admin = await an_admin(db_session)
    await db_session.commit()

    item = (await client.get(list_url(interview), headers=headers(admin))).json()["items"][0]

    assert item["interview_score"] is None and item["interview_status"] == "UPLOADED"


@pytest.mark.asyncio
async def test_an_admin_opens_an_interview_of_another_account_and_gets_the_review_data(client, db_session):
    interview = await scored_at(db_session, 58)
    admin = await an_admin(db_session)
    await db_session.commit()

    body = await detail(client, interview, admin)

    assert body["ai_score"] == 58
    assert body["score_review"]["original_score"] == 58
    # The company's own view of the same interview carries no review data.
    assert (await detail(client, interview, interview.employer))["score_review"] is None


@pytest.mark.asyncio
async def test_a_stranger_still_cannot_open_another_accounts_interview(client, db_session):
    interview = await scored_at(db_session, 58)
    stranger = make_employer()
    db_session.add(stranger)
    await db_session.commit()

    resp = await client.get(
        "/api/v1/interviews/detail",
        params={"job_id": str(interview.job.id), "talent_pool_profile_id": str(interview.interview.talent_pool_profile_id)},
        headers=headers(stranger),
    )

    assert resp.status_code == 403
