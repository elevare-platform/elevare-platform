"""The candidate's screen reports that sending the recording failed.

The file goes from the browser straight to storage, so before this a failed upload left no trace
on our side and "the recording never arrived" could not be explained. The report is one log line
(``interview_upload_failure``); it stores nothing and changes nothing about the interview."""

import logging
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from .test_interview_router import register_and_promote
from .test_strict_interview import _base, make_strict

REPORT = {"stage": "file", "reason": "blocked_or_dropped", "http_status": 0, "attempt": 2, "size_bytes": 31_000_000}


def _url(token):
    return f"{_base(token)}/upload-failure"


@pytest.mark.asyncio
async def test_a_failed_upload_is_logged_with_what_the_browser_saw(client, db_session, caplog):
    interview = await make_strict(db_session)

    with caplog.at_level(logging.WARNING, logger="app.modules.interviews.service"):
        resp = await client.post(_url(interview.token), json=REPORT)

    assert resp.status_code == 204 and resp.content == b""
    [line] = [r.getMessage() for r in caplog.records if "interview_upload_failure" in r.getMessage()]
    assert str(interview.interview.id) in line and str(interview.job.id) in line
    for fragment in ("stage=file", "reason=blocked_or_dropped", "http_status=0", "attempt=2", "size_bytes=31000000"):
        assert fragment in line


@pytest.mark.asyncio
async def test_reporting_a_failure_changes_nothing_about_the_interview(client, db_session):
    interview = await make_strict(db_session)
    before = (interview.interview.status, interview.interview.r2_key, interview.interview.updated_at)

    await client.post(_url(interview.token), json=REPORT)

    await db_session.refresh(interview.interview)
    assert (interview.interview.status, interview.interview.r2_key, interview.interview.updated_at) == before


@pytest.mark.asyncio
async def test_only_the_fields_that_are_known_are_accepted(client, db_session):
    interview = await make_strict(db_session)

    for bad in (
        {**REPORT, "reason": "the candidate was rude"},
        {**REPORT, "stage": "somewhere"},
        {**REPORT, "http_status": 1000},
        {**REPORT, "attempt": 0},
        {**REPORT, "size_bytes": -1},
        {"reason": "timeout"},
    ):
        assert (await client.post(_url(interview.token), json=bad)).status_code == 422


@pytest.mark.asyncio
async def test_a_minimal_report_is_enough(client, db_session):
    interview = await make_strict(db_session)

    resp = await client.post(_url(interview.token), json={"stage": "url", "reason": "server_error"})

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_an_unknown_or_expired_link_is_refused_and_logs_nothing(client, db_session, caplog):
    interview = await make_strict(db_session)
    interview.interview.token_expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.commit()

    with caplog.at_level(logging.WARNING, logger="app.modules.interviews.service"):
        unknown = await client.post(_url("not-a-real-token"), json=REPORT)
        expired = await client.post(_url(interview.token), json=REPORT)

    assert unknown.status_code == 404
    assert expired.status_code == 422
    assert not [r for r in caplog.records if "interview_upload_failure" in r.getMessage()]


@pytest.mark.asyncio
async def test_a_logged_in_candidate_needs_to_be_signed_in_and_to_own_the_application(client, db_session):
    anonymous = await client.post(f"/api/v1/interviews/applications/{uuid4()}/upload-failure", json=REPORT)
    token, _user = await register_and_promote(client, db_session, "CANDIDATE")
    someone_elses = await client.post(
        f"/api/v1/interviews/applications/{uuid4()}/upload-failure",
        json=REPORT,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert anonymous.status_code in (401, 403)
    assert someone_elses.status_code == 404
