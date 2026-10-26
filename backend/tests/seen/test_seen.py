"""Which CVs have been looked at (docs/08_DECISIONS.md, item 35): the employer's Talent Pool page
and the shared link an outside reader opens."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select, update

from app.core.exceptions import JobNotFoundError
from app.core.storage import MockStorageService
from app.modules.auth.jwt_handler import create_token_pair
from app.modules.jobs.access_token_repository import AccessTokenRepository
from app.modules.jobs.access_token_schema import CreateAccessTokenRequest
from app.modules.jobs.access_token_service import AccessTokenService
from app.modules.seen import service as seen_service
from app.modules.seen.models import (
    SharedLinkItemView,
    SharedLinkVisit,
    TalentPoolProfileView,
)
from app.modules.seen.service import SeenService, item_key, valid_item_key
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.service import TalentPoolService
from tests.conftest import (
    make_employer,
    make_job,
    make_organization_for,
    make_subscription_for,
)

T0 = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def mock_storage():
    with patch("app.modules.jobs.access_token_service.get_storage_service", return_value=MockStorageService()):
        yield


async def employer_with_plan(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    await make_subscription_for(db_session, organization)  # Professional: no five-CV cap
    return employer


async def cv(db_session, added_by, created_at, **over):
    fields = {"source": "other", "status": "new", **over}
    profile = TalentPoolProfiles(added_by=added_by, created_at=created_at, **fields)
    db_session.add(profile)
    await db_session.flush()
    return profile


def headers(user):
    return {"Authorization": f"Bearer {create_token_pair(user.id, user.role)['access_token']}"}


async def listing(db_session, employer, **kwargs):
    service = TalentPoolService(db_session, cv_service=None)
    return await service.list_profiles(
        status=None, source=None, job_id=None, cursor=None, limit=50, current_user=employer, **kwargs
    )


# ---------------------------------------------------------------------------
# The employer's Talent Pool page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_cv_added_after_the_employer_started_is_new_until_they_open_it(db_session):
    employer = await employer_with_plan(db_session)
    await SeenService(db_session).baseline(employer.id, now=T0)
    fresh = await cv(db_session, employer.id, T0 + timedelta(hours=1))

    before = {item.id: item.is_new for item in (await listing(db_session, employer))["items"]}
    await SeenService(db_session).mark_profile_opened(employer.id, fresh.id)
    after = {item.id: item.is_new for item in (await listing(db_session, employer))["items"]}

    assert before == {fresh.id: True}
    assert after == {fresh.id: False}


@pytest.mark.asyncio
async def test_a_cv_the_employer_already_had_when_they_started_is_never_new(db_session):
    """Switching the markers on must not flag every CV someone already had."""
    employer = await employer_with_plan(db_session)
    await SeenService(db_session).baseline(employer.id, now=T0)
    old = await cv(db_session, employer.id, T0 - timedelta(days=30))

    [item] = (await listing(db_session, employer))["items"]

    assert item.id == old.id and item.is_new is False


@pytest.mark.asyncio
async def test_the_first_time_the_page_is_used_sets_the_starting_point_to_now(db_session):
    employer = await employer_with_plan(db_session)
    existing = await cv(db_session, employer.id, datetime.now(UTC) - timedelta(days=3))

    result = await listing(db_session, employer)

    assert [(item.id, item.is_new) for item in result["items"]] == [(existing.id, False)]
    baseline = (
        await db_session.execute(
            select(seen_service.EmployerSeenBaseline.baseline_at).where(
                seen_service.EmployerSeenBaseline.employer_id == employer.id
            )
        )
    ).scalar_one()
    assert abs((datetime.now(UTC) - baseline).total_seconds()) < 60
    # Asking again does not move it.
    await listing(db_session, employer)
    again = (
        await db_session.execute(
            select(seen_service.EmployerSeenBaseline.baseline_at).where(
                seen_service.EmployerSeenBaseline.employer_id == employer.id
            )
        )
    ).scalar_one()
    assert again == baseline


@pytest.mark.asyncio
async def test_only_the_new_ones_can_be_asked_for_and_counted(db_session):
    employer = await employer_with_plan(db_session)
    await SeenService(db_session).baseline(employer.id, now=T0)
    await cv(db_session, employer.id, T0 - timedelta(days=1))  # before: not new
    opened = await cv(db_session, employer.id, T0 + timedelta(hours=1))
    unopened_a = await cv(db_session, employer.id, T0 + timedelta(hours=2))
    unopened_b = await cv(db_session, employer.id, T0 + timedelta(hours=3))
    await SeenService(db_session).mark_profile_opened(employer.id, opened.id)

    only_new = await listing(db_session, employer, unseen=True)
    everything = await listing(db_session, employer)
    count = await TalentPoolService(db_session, cv_service=None).new_count(employer)

    assert {item.id for item in only_new["items"]} == {unopened_a.id, unopened_b.id}
    assert all(item.is_new for item in only_new["items"])
    assert len(everything["items"]) == 4
    assert count == 2


@pytest.mark.asyncio
async def test_opening_a_cv_is_remembered_once_however_often_it_is_opened(db_session):
    employer = await employer_with_plan(db_session)
    await SeenService(db_session).baseline(employer.id, now=T0)
    profile = await cv(db_session, employer.id, T0 + timedelta(hours=1))
    service = TalentPoolService(db_session, cv_service=None)

    await service.mark_seen(profile.id, employer)
    await service.mark_seen(profile.id, employer)

    rows = (await db_session.execute(select(TalentPoolProfileView))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_what_one_employer_opens_stays_new_for_another(db_session):
    """An admin-added CV is in every employer's list; each employer has their own markers."""
    from tests.conftest import make_user

    admin = make_user(role="ADMIN")
    db_session.add(admin)
    first = await employer_with_plan(db_session)
    second = await employer_with_plan(db_session)
    await db_session.flush()
    await SeenService(db_session).baseline(first.id, now=T0)
    await SeenService(db_session).baseline(second.id, now=T0)
    shared = await cv(db_session, admin.id, T0 + timedelta(hours=1))

    await TalentPoolService(db_session, cv_service=None).mark_seen(shared.id, first)

    assert [i.is_new for i in (await listing(db_session, first))["items"]] == [False]
    assert [i.is_new for i in (await listing(db_session, second))["items"]] == [True]


@pytest.mark.asyncio
async def test_a_cv_the_employer_cannot_see_cannot_be_marked_and_leaves_nothing_behind(db_session):
    from app.core.exceptions import ProfileNotFoundException

    mine = await employer_with_plan(db_session)
    other = await employer_with_plan(db_session)
    theirs = await cv(db_session, other.id, T0 + timedelta(hours=1))

    with pytest.raises(ProfileNotFoundException):
        await TalentPoolService(db_session, cv_service=None).mark_seen(theirs.id, mine)

    assert (await db_session.execute(select(TalentPoolProfileView))).scalars().all() == []


@pytest.mark.asyncio
async def test_the_routes_work_over_http(client, db_session):
    employer = await employer_with_plan(db_session)
    await SeenService(db_session).baseline(employer.id, now=T0)
    profile = await cv(db_session, employer.id, T0 + timedelta(hours=1))

    count = await client.get("/api/v1/talent-pool/new-count", headers=headers(employer))
    marked = await client.post(f"/api/v1/talent-pool/{profile.id}/seen", headers=headers(employer))
    after = await client.get("/api/v1/talent-pool/new-count", headers=headers(employer))
    unseen = await client.get("/api/v1/talent-pool?unseen=true", headers=headers(employer))

    assert count.json() == {"count": 1}
    assert marked.status_code == 200 and marked.json() == {"seen": True}
    assert after.json() == {"count": 0}
    assert unseen.json()["items"] == []
    assert (await client.post(f"/api/v1/talent-pool/{profile.id}/seen")).status_code == 401


@pytest.mark.asyncio
async def test_an_email_typed_for_an_interview_is_not_counted_as_a_new_cv(db_session):
    employer = await employer_with_plan(db_session)
    await SeenService(db_session).baseline(employer.id, now=T0)
    await cv(db_session, employer.id, T0 + timedelta(hours=1), source="interview_invite", override_email="a@b.com")

    assert await TalentPoolService(db_session, cv_service=None).new_count(employer) == 0


# ---------------------------------------------------------------------------
# The shared link
# ---------------------------------------------------------------------------


async def shared_job(db_session):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    return employer, job


async def external_cv(db_session, employer, job, scored_at, score=70):
    profile = TalentPoolProfiles(
        added_by=employer.id, source="other", status="new", sourced_for_job_id=job.id, ai_score=score,
        ai_score_computed_at=scored_at, created_at=scored_at,
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


async def new_link(db_session, employer, job):
    response = await AccessTokenService(db_session).create_access_token(
        job.id, CreateAccessTokenRequest(expires_in_days=7), employer
    )
    token = await AccessTokenRepository(db_session).get_by_id(response.id)
    return token


async def visit(db_session, token):
    return await AccessTokenService(db_session).get_public_applicants(token.token)


@pytest.mark.asyncio
async def test_a_first_visit_shows_every_candidate_as_unseen_and_nothing_as_new_since_last_time(db_session):
    employer, job = await shared_job(db_session)
    now = datetime.now(UTC)
    await external_cv(db_session, employer, job, now - timedelta(days=2))
    await external_cv(db_session, employer, job, now - timedelta(days=1), score=60)
    token = await new_link(db_session, employer, job)

    result = await visit(db_session, token)

    assert result.unseen_count == 2 and result.new_since_last_visit_count == 0
    assert result.previous_visit_at is None
    assert all(valid_item_key(item.item_key) and item.is_unseen for item in result.applicants)
    assert not any(item.is_new_since_last_visit for item in result.applicants)


@pytest.mark.asyncio
async def test_the_key_is_the_same_on_every_visit_to_one_link_and_different_on_another_link(db_session):
    employer, job = await shared_job(db_session)
    profile = await external_cv(db_session, employer, job, datetime.now(UTC) - timedelta(days=1))
    first_link = await new_link(db_session, employer, job)
    second_link = await new_link(db_session, employer, job)

    a1 = (await visit(db_session, first_link)).applicants[0].item_key
    a2 = (await visit(db_session, first_link)).applicants[0].item_key
    b = (await visit(db_session, second_link)).applicants[0].item_key

    assert a1 == a2 and a1 != b
    assert str(profile.id).replace("-", "")[:16] != a1  # not the candidate's own id
    assert a1 == item_key(first_link.id, "external", profile.id)


@pytest.mark.asyncio
async def test_a_candidate_the_reader_opened_stops_being_unseen_on_that_link_only(db_session):
    employer, job = await shared_job(db_session)
    await external_cv(db_session, employer, job, datetime.now(UTC) - timedelta(days=2))
    await external_cv(db_session, employer, job, datetime.now(UTC) - timedelta(days=1), score=60)
    link = await new_link(db_session, employer, job)
    other_link = await new_link(db_session, employer, job)
    key = (await visit(db_session, link)).applicants[0].item_key
    service = AccessTokenService(db_session)

    await service.mark_item_seen(link.token, key)
    await service.mark_item_seen(link.token, key)  # again: nothing changes

    again = await visit(db_session, link)
    elsewhere = await visit(db_session, other_link)
    assert again.unseen_count == 1
    assert [item.is_unseen for item in again.applicants] == [False, True]
    assert elsewhere.unseen_count == 2
    rows = (await db_session.execute(select(SharedLinkItemView))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_someone_returning_days_later_is_told_what_arrived_since_their_last_visit(db_session):
    employer, job = await shared_job(db_session)
    now = datetime.now(UTC)
    old = await external_cv(db_session, employer, job, now - timedelta(days=10))
    link = await new_link(db_session, employer, job)
    await visit(db_session, link)  # the first visit, a while ago
    await db_session.execute(
        update(SharedLinkVisit).where(SharedLinkVisit.token_id == link.id).values(last_visit_at=now - timedelta(days=7))
    )
    fresh = await external_cv(db_session, employer, job, now - timedelta(hours=1), score=80)

    result = await visit(db_session, link)

    by_id = {item.item_key: item for item in result.applicants}
    assert by_id[item_key(link.id, "external", fresh.id)].is_new_since_last_visit is True
    assert by_id[item_key(link.id, "external", old.id)].is_new_since_last_visit is False
    assert result.new_since_last_visit_count == 1
    assert result.previous_visit_at is not None and result.previous_visit_at < now - timedelta(days=6)


@pytest.mark.asyncio
async def test_reloading_the_page_does_not_lose_what_is_new(db_session):
    employer, job = await shared_job(db_session)
    now = datetime.now(UTC)
    link = await new_link(db_session, employer, job)
    await visit(db_session, link)
    await db_session.execute(
        update(SharedLinkVisit).where(SharedLinkVisit.token_id == link.id).values(last_visit_at=now - timedelta(days=3))
    )
    fresh = await external_cv(db_session, employer, job, now - timedelta(hours=2))

    first = await visit(db_session, link)
    reloaded = await visit(db_session, link)  # seconds later: the same visit

    key = item_key(link.id, "external", fresh.id)
    assert {i.item_key: i.is_new_since_last_visit for i in first.applicants}[key] is True
    assert {i.item_key: i.is_new_since_last_visit for i in reloaded.applicants}[key] is True
    assert first.previous_visit_at == reloaded.previous_visit_at


@pytest.mark.asyncio
async def test_a_visit_after_the_gap_becomes_the_new_previous_visit(db_session):
    link_id = None
    employer, job = await shared_job(db_session)
    link = await new_link(db_session, employer, job)
    link_id = link.id
    seen = SeenService(db_session)

    assert await seen.record_visit(link_id, now=T0) is None
    assert await seen.record_visit(link_id, now=T0 + timedelta(minutes=10)) is None  # same visit
    assert await seen.record_visit(link_id, now=T0 + timedelta(days=1)) == T0 + timedelta(minutes=10)
    assert await seen.record_visit(link_id, now=T0 + timedelta(days=1, minutes=5)) == T0 + timedelta(minutes=10)


@pytest.mark.asyncio
async def test_a_made_up_key_is_ignored_and_a_link_cannot_be_made_to_remember_without_limit(db_session, monkeypatch):
    employer, job = await shared_job(db_session)
    link = await new_link(db_session, employer, job)
    service = AccessTokenService(db_session)
    monkeypatch.setattr(seen_service, "MAX_OPENED_PER_LINK", 2)

    for bad in ["", "short", "g" * 16, "A" * 16, "0" * 17, "../../etc/passwd"]:
        await service.mark_item_seen(link.token, bad)
    for good in ["a" * 16, "b" * 16, "c" * 16]:
        await service.mark_item_seen(link.token, good)

    keys = {row.item_key for row in (await db_session.execute(select(SharedLinkItemView))).scalars().all()}
    assert keys == {"a" * 16, "b" * 16}


@pytest.mark.asyncio
async def test_an_invalid_link_cannot_mark_anything(db_session):
    with pytest.raises(JobNotFoundError):
        await AccessTokenService(db_session).mark_item_seen("not-a-token", "a" * 16)


@pytest.mark.asyncio
async def test_the_public_routes_work_over_http_without_logging_in(client, db_session):
    employer, job = await shared_job(db_session)
    await external_cv(db_session, employer, job, datetime.now(UTC) - timedelta(days=1))
    link = await new_link(db_session, employer, job)

    listed = await client.get(f"/api/v1/public/jobs/{link.token}/applicants")
    key = listed.json()["applicants"][0]["item_key"]
    marked = await client.post(f"/api/v1/public/jobs/{link.token}/seen", json={"item_key": key})
    after = await client.get(f"/api/v1/public/jobs/{link.token}/applicants")
    refused = await client.post("/api/v1/public/jobs/nope/seen", json={"item_key": key})

    assert listed.json()["unseen_count"] == 1
    assert marked.status_code == 200
    assert after.json()["unseen_count"] == 0
    assert after.json()["applicants"][0]["is_unseen"] is False
    assert refused.status_code == 404


# ---------------------------------------------------------------------------
# The employer's applicants list for a job
# ---------------------------------------------------------------------------


async def applicant(db_session, job, created_at):
    """A candidate who applied to ``job`` at ``created_at``."""
    from app.modules.applications.models import Application
    from tests.conftest import make_user

    candidate = make_user(role="CANDIDATE")
    db_session.add(candidate)
    await db_session.flush()
    application = Application(candidate_id=candidate.id, job_id=job.id, status="SUBMITTED", created_at=created_at)
    db_session.add(application)
    await db_session.flush()
    return application


async def applicants_of(db_session, employer, job, **kwargs):
    from app.modules.applications.schema import ApplicationFilters
    from app.modules.applications.service import ApplicationService

    return await ApplicationService(db_session).get_job_applicants(
        job.id, employer.id, employer.role, ApplicationFilters(), None, 50, **kwargs
    )


@pytest.mark.asyncio
async def test_an_application_made_after_the_employer_started_is_new_until_they_open_it(db_session):
    from app.modules.applications.service import ApplicationService

    employer = await employer_with_plan(db_session)
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    await SeenService(db_session).baseline(employer.id, now=T0)
    old = await applicant(db_session, job, T0 - timedelta(days=2))
    fresh = await applicant(db_session, job, T0 + timedelta(hours=1))

    before = {a.id: a.is_new for a in (await applicants_of(db_session, employer, job)).items}
    await ApplicationService(db_session).mark_applicant_seen(fresh.id, employer.id, employer.role)
    after = {a.id: a.is_new for a in (await applicants_of(db_session, employer, job)).items}

    assert before == {old.id: False, fresh.id: True}
    assert after == {old.id: False, fresh.id: False}


@pytest.mark.asyncio
async def test_only_the_new_applicants_can_be_asked_for_and_counted(db_session):
    from app.modules.applications.service import ApplicationService

    employer = await employer_with_plan(db_session)
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    await SeenService(db_session).baseline(employer.id, now=T0)
    await applicant(db_session, job, T0 - timedelta(days=1))
    opened = await applicant(db_session, job, T0 + timedelta(hours=1))
    waiting = await applicant(db_session, job, T0 + timedelta(hours=2))
    service = ApplicationService(db_session)
    await service.mark_applicant_seen(opened.id, employer.id, employer.role)

    only_new = await applicants_of(db_session, employer, job, unseen=True)
    everyone = await applicants_of(db_session, employer, job)
    count = await service.new_applicants_count(job.id, employer.id, employer.role)

    assert [a.id for a in only_new.items] == [waiting.id]
    assert len(everyone.items) == 3
    assert count == 1


@pytest.mark.asyncio
async def test_an_employers_first_look_at_the_list_starts_with_nothing_new(db_session):
    employer = await employer_with_plan(db_session)
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    await applicant(db_session, job, datetime.now(UTC) - timedelta(days=1))

    result = await applicants_of(db_session, employer, job)

    assert [a.is_new for a in result.items] == [False]


@pytest.mark.asyncio
async def test_another_employers_applicant_cannot_be_marked_or_counted(db_session):
    from app.core.exceptions import ApplicationNotFound, PermissionDeniedException
    from app.modules.applications.service import ApplicationService

    mine = await employer_with_plan(db_session)
    other = await employer_with_plan(db_session)
    job = make_job(other.id)
    db_session.add(job)
    await db_session.flush()
    theirs = await applicant(db_session, job, T0 + timedelta(hours=1))
    service = ApplicationService(db_session)

    with pytest.raises(ApplicationNotFound):
        await service.mark_applicant_seen(theirs.id, mine.id, mine.role)
    with pytest.raises(PermissionDeniedException):
        await service.new_applicants_count(job.id, mine.id, mine.role)

    from app.modules.seen.models import ApplicationView

    assert (await db_session.execute(select(ApplicationView))).scalars().all() == []


@pytest.mark.asyncio
async def test_the_applicant_routes_work_over_http(client, db_session):
    employer = await employer_with_plan(db_session)
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()
    await SeenService(db_session).baseline(employer.id, now=T0)
    fresh = await applicant(db_session, job, T0 + timedelta(hours=1))

    count = await client.get(f"/api/v1/applications/job/{job.id}/new-count", headers=headers(employer))
    marked = await client.post(f"/api/v1/applications/{fresh.id}/seen", headers=headers(employer))
    again = await client.post(f"/api/v1/applications/{fresh.id}/seen", headers=headers(employer))
    after = await client.get(f"/api/v1/applications/job/{job.id}/new-count", headers=headers(employer))
    unseen = await client.get(f"/api/v1/applications/job/{job.id}?unseen=true", headers=headers(employer))

    assert count.json() == {"count": 1}
    assert marked.json() == {"seen": True} and again.status_code == 200
    assert after.json() == {"count": 0}
    assert unseen.json()["items"] == []
    assert (await client.post(f"/api/v1/applications/{fresh.id}/seen")).status_code == 401
