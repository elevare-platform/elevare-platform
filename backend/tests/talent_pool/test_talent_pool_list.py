"""Tests for ``TalentPoolRepository.list`` ordering, pagination and filters."""

from datetime import UTC, datetime, timedelta

import pytest

from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.repository import TalentPoolRepository
from tests.conftest import make_employer, make_job
from tests.talent_pool.test_talent_pool_service import register_and_activate


async def _make_pool(db_session, spec, employer=None):
    """Create a job and pool rows for ``spec`` (and an employer unless given).

    ``spec`` is a list of ``(key, score, days_since_added)``. ``created_at`` is
    passed explicitly because the database would otherwise give every row in a
    test transaction the same timestamp. Returns ``(employer, job, rows_by_key)``.
    """
    if employer is None:
        employer = make_employer()
        db_session.add(employer)
        await db_session.flush()
    job = make_job(employer.id)
    db_session.add(job)
    await db_session.flush()

    now = datetime.now(UTC)
    rows = {}
    for key, score, age_days in spec:
        row = TalentPoolProfiles(
            added_by=employer.id,
            sourced_for_job_id=job.id,
            ai_score=score,
            created_at=now - timedelta(days=age_days),
        )
        db_session.add(row)
        rows[key] = row
    await db_session.flush()
    return employer, job, rows


async def test_list_by_score_returns_every_row_once_in_order(db_session):
    # Age is deliberately NOT aligned with score, so a date-only cursor would skip rows.
    employer, job, rows = await _make_pool(
        db_session,
        [("a", 90, 10), ("b", 90, 5), ("c", 70, 1), ("d", 55, 8), ("e", None, 3)],
    )

    repo = TalentPoolRepository(db_session)
    seen, cursor = [], None
    for _ in range(10):  # guard: a broken cursor must fail, not loop forever
        page = await repo.list(
            job_id=job.id, cursor=cursor, limit=2, viewer_id=employer.id
        )
        seen += [p.id for p in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break

    # score desc; the two 90s tie-break newest first (b before a); unscored last
    assert seen == [rows[k].id for k in ("b", "a", "c", "d", "e")]


async def test_list_added_within_days_keeps_only_recent_rows(db_session):
    employer, job, rows = await _make_pool(
        db_session,
        [("new", 80, 1), ("mid", 60, 10), ("old", 90, 40)],
    )

    repo = TalentPoolRepository(db_session)
    page = await repo.list(job_id=job.id, viewer_id=employer.id, added_within_days=14)

    # "old" has the best score but was added 40 days ago, so it is excluded
    assert [p.id for p in page["items"]] == [rows["new"].id, rows["mid"].id]
    assert page["total"] == 2


async def test_list_sort_newest_overrides_score_order(db_session):
    employer, job, rows = await _make_pool(
        db_session,
        [("old_best", 90, 10), ("newest", 50, 1), ("mid", 70, 5)],
    )

    repo = TalentPoolRepository(db_session)
    by_newest = await repo.list(job_id=job.id, viewer_id=employer.id, sort="newest")
    by_score = await repo.list(job_id=job.id, viewer_id=employer.id, sort="score")
    default = await repo.list(job_id=job.id, viewer_id=employer.id)

    assert [p.id for p in by_newest["items"]] == [
        rows[k].id for k in ("newest", "mid", "old_best")
    ]
    assert [p.id for p in by_score["items"]] == [
        rows[k].id for k in ("old_best", "mid", "newest")
    ]
    # No sort given: unchanged behaviour (score order when a job is selected)
    assert [p.id for p in default["items"]] == [p.id for p in by_score["items"]]


async def test_list_min_score_is_inclusive_and_hides_unscored(db_session):
    employer, job, rows = await _make_pool(
        db_session,
        [("high", 80, 1), ("edge", 55, 2), ("below", 54, 3), ("unscored", None, 4)],
    )

    repo = TalentPoolRepository(db_session)
    page = await repo.list(job_id=job.id, viewer_id=employer.id, min_score=55)

    # 55 counts as strong; 54 does not; a NULL score can never be "at least 55"
    assert [p.id for p in page["items"]] == [rows["high"].id, rows["edge"].id]
    assert page["total"] == 2


async def test_list_endpoint_applies_filters_and_sort(client, db_session):
    token, employer = await register_and_activate(client, db_session, "EMPLOYER")
    _, job, rows = await _make_pool(
        db_session,
        [("new", 80, 1), ("mid", 60, 10), ("old", 90, 40), ("weak", 30, 2)],
        employer=employer,
    )

    resp = await client.get(
        "/api/v1/talent-pool",
        params={
            "job_id": str(job.id),
            "sort": "newest",
            "min_score": 55,
            "added_within_days": 14,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    # "old" fails the recency filter, "weak" fails min_score; newest first
    assert [i["id"] for i in resp.json()["items"]] == [
        str(rows["new"].id),
        str(rows["mid"].id),
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"sort": "bogus"},
        {"min_score": 101},
        {"min_score": -1},
        {"added_within_days": 0},
        {"added_within_days": 366},
    ],
)
async def test_list_endpoint_rejects_invalid_params(client, db_session, params):
    token, _ = await register_and_activate(client, db_session, "EMPLOYER")

    resp = await client.get(
        "/api/v1/talent-pool",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 422
