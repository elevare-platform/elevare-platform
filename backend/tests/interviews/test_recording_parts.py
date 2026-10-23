"""A strict interview whose page reloads must not lose what was recorded before the reload.

The browser keeps the recording in its own storage and, when the candidate comes back, uploads
it as a separate "part" (this file: asking for where to upload it, and joining the parts with
the final recording before scoring). The join itself is tested with real ffmpeg in
``test_recording_merge.py``; here it is replaced by a fake so the logic around it can be
checked: which pieces, in which order, what is deleted, and what happens when something fails."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.modules.interviews import service as service_module
from app.modules.interviews import tasks as tasks_module
from app.modules.interviews.enums import InterviewStatus
from app.modules.interviews.models import StrictInterviewRun
from app.modules.interviews.recording_merge import merge_key, part_key
from app.modules.interviews.repository import InterviewRepository

from .test_strict_interview import _base, _logged_in_strict, make_strict


async def _run(db_session, interview):
    return (
        await db_session.execute(
            select(StrictInterviewRun).where(StrictInterviewRun.interview_id == interview.id)
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# Asking where to upload an earlier recording
# ---------------------------------------------------------------------------


@pytest.fixture
def storage_urls(monkeypatch):
    storage = MagicMock()
    storage.generate_presigned_upload_url = AsyncMock(side_effect=lambda key, *_: f"https://r2.test/{key}")
    monkeypatch.setattr(service_module, "get_storage_service", lambda: storage)
    return storage


async def part(client, token):
    return await client.post(f"{_base(token)}/strict/recording-part")


@pytest.mark.asyncio
async def test_each_ask_gets_the_next_part_number_and_its_own_upload_address(
    client, db_session, storage_urls
):
    interview = await make_strict(db_session)

    first = (await part(client, interview.token)).json()
    second = (await part(client, interview.token)).json()

    assert (first["part"], second["part"]) == (1, 2)
    assert first["upload_url"] == f"https://r2.test/{part_key(interview.interview.id, 1)}"
    assert second["upload_url"] == f"https://r2.test/{part_key(interview.interview.id, 2)}"
    assert first["expires_in_seconds"] > 0
    assert (await _run(db_session, interview.interview)).recording_parts == 2


@pytest.mark.asyncio
async def test_a_part_is_asked_for_in_a_started_or_a_waiting_interview_only(
    client, db_session, storage_urls
):
    done = await make_strict(db_session, status=InterviewStatus.UPLOADED.value)

    resp = await part(client, done.token)

    assert resp.status_code == 422
    storage_urls.generate_presigned_upload_url.assert_not_called()
    assert (await _run(db_session, done.interview)).recording_parts == 0


@pytest.mark.asyncio
async def test_a_live_interview_has_no_parts(client, db_session, storage_urls):
    live = await make_strict(db_session, strict=False)

    resp = await part(client, live.token)

    assert resp.status_code == 422
    assert resp.json()["code"] == "INTERVIEW_WRONG_STYLE"


@pytest.mark.asyncio
async def test_the_number_of_parts_is_capped(client, db_session, storage_urls, monkeypatch):
    monkeypatch.setattr(settings, "strict_recording_max_parts", 2)
    interview = await make_strict(db_session)
    await part(client, interview.token)
    await part(client, interview.token)

    resp = await part(client, interview.token)

    assert resp.status_code == 422
    assert resp.json()["code"] == "INTERVIEW_TOO_MANY_PARTS"
    assert (await _run(db_session, interview.interview)).recording_parts == 2


@pytest.mark.asyncio
async def test_an_unknown_link_gets_no_upload_address(client, storage_urls):
    resp = await part(client, "no-such-token")

    assert resp.status_code == 404
    storage_urls.generate_presigned_upload_url.assert_not_called()


@pytest.mark.asyncio
async def test_the_off_switch_stops_this_too(client, db_session, storage_urls, monkeypatch):
    interview = await make_strict(db_session)
    monkeypatch.setattr(settings, "interview_enabled", False)

    resp = await part(client, interview.token)

    assert resp.status_code >= 400
    storage_urls.generate_presigned_upload_url.assert_not_called()


@pytest.mark.asyncio
async def test_a_logged_in_candidate_asks_the_same_way_and_another_candidate_cannot(
    client, db_session, storage_urls
):
    from .test_interview_router import register_and_promote

    token, application = await _logged_in_strict(client, db_session)
    url = f"/api/v1/interviews/applications/{application.id}/strict/recording-part"

    own = await client.post(url, headers={"Authorization": f"Bearer {token}"})
    intruder_token, _ = await register_and_promote(client, db_session, "CANDIDATE")
    other = await client.post(url, headers={"Authorization": f"Bearer {intruder_token}"})

    assert own.status_code == 201 and own.json()["part"] == 1
    assert other.status_code == 403


# ---------------------------------------------------------------------------
# Joining the parts before scoring
# ---------------------------------------------------------------------------


class MemoryStorage:
    """A bucket in a dict, that records what was joined and what was deleted."""

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.deleted = []
        self.fail_upload = False

    async def get_object_size(self, key):
        return len(self.files[key]) if key in self.files else None

    async def download_file(self, key):
        return self.files[key]

    async def upload_file(self, data, key, content_type):
        if self.fail_upload:
            raise RuntimeError("the bucket is down")
        self.files[key] = data
        return key

    async def delete_file(self, key):
        self.deleted.append(key)
        self.files.pop(key, None)


@pytest.fixture
def join(monkeypatch):
    """The bucket and the join, replaced. The fake join glues the bytes in the order given."""
    state = {"storage": MemoryStorage(), "calls": [], "fail": False}

    async def fake_concat(recordings):
        state["calls"].append(list(recordings))
        if state["fail"]:
            raise RuntimeError("ffmpeg could not join the recordings")
        return b"+".join(recordings)

    monkeypatch.setattr(tasks_module, "get_storage_service", lambda: state["storage"])
    monkeypatch.setattr(tasks_module, "concat_recordings", fake_concat)
    return state


async def _interview_with_parts(db_session, join_state, parts, *, uploaded=(1, 2, 3)):
    interview = await make_strict(db_session, status=InterviewStatus.UPLOADED.value)
    interview.interview.r2_key = f"interviews/{interview.interview.id}/recording.webm"
    run = await _run(db_session, interview.interview)
    run.recording_parts = parts
    await db_session.commit()
    files = {interview.interview.r2_key: b"FINAL"}
    for number in uploaded:
        if number <= parts:
            files[part_key(interview.interview.id, number)] = f"P{number}".encode()
    join_state["storage"].files.update(files)
    return interview


async def _merge(db_session, interview):
    repo = InterviewRepository(db_session)
    loaded = await repo.get_by_id(interview.interview.id)
    return await tasks_module._merge_recording_parts(db_session, repo, loaded)


@pytest.mark.asyncio
async def test_the_parts_and_the_final_recording_become_one_video_in_that_order(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=2)
    original = interview.interview.r2_key

    merged = await _merge(db_session, interview)

    new_key = merge_key(interview.interview.id)
    assert join["calls"] == [[b"P1", b"P2", b"FINAL"]]
    assert merged.r2_key == new_key
    assert join["storage"].files[new_key] == b"P1+P2+FINAL"
    # The pieces are gone once the joined video is in place, and nothing else was touched.
    assert set(join["storage"].deleted) == {part_key(interview.interview.id, 1), part_key(interview.interview.id, 2), original}
    assert set(join["storage"].files) == {new_key}
    assert (await _run(db_session, interview.interview)).recording_parts == 0


@pytest.mark.asyncio
async def test_an_interview_that_was_never_interrupted_is_left_alone(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=0)

    merged = await _merge(db_session, interview)

    assert join["calls"] == [] and join["storage"].deleted == []
    assert merged.r2_key == interview.interview.r2_key


@pytest.mark.asyncio
async def test_a_live_interview_is_left_alone(db_session, join):
    live = await make_strict(db_session, strict=False, status=InterviewStatus.UPLOADED.value, r2_key="x/recording.webm")
    join["storage"].files["x/recording.webm"] = b"FINAL"

    merged = await _merge(db_session, live)

    assert join["calls"] == [] and merged.r2_key == "x/recording.webm"


@pytest.mark.asyncio
async def test_a_part_that_never_arrived_is_skipped_and_the_rest_are_joined(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=3, uploaded=(2, 3))

    merged = await _merge(db_session, interview)

    assert join["calls"] == [[b"P2", b"P3", b"FINAL"]]
    assert merged.r2_key == merge_key(interview.interview.id)
    assert (await _run(db_session, interview.interview)).recording_parts == 0


@pytest.mark.asyncio
async def test_when_no_part_arrived_the_final_recording_stays_as_it_is(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=2, uploaded=())
    original = interview.interview.r2_key

    merged = await _merge(db_session, interview)

    assert join["calls"] == [] and join["storage"].deleted == []
    assert merged.r2_key == original
    assert join["storage"].files[original] == b"FINAL"
    assert (await _run(db_session, interview.interview)).recording_parts == 0


@pytest.mark.asyncio
async def test_a_join_that_fails_keeps_every_piece_and_never_stops_the_scoring(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=2)
    original = interview.interview.r2_key
    join["fail"] = True

    merged = await _merge(db_session, interview)

    assert merged.r2_key == original
    assert join["storage"].deleted == []
    assert set(join["storage"].files) == {
        original, part_key(interview.interview.id, 1), part_key(interview.interview.id, 2)
    }
    # Still marked as having parts, so the join can be run again.
    assert (await _run(db_session, interview.interview)).recording_parts == 2


@pytest.mark.asyncio
async def test_a_final_recording_that_will_not_join_does_not_cost_the_real_parts(
    db_session, join, monkeypatch
):
    """A reload just after the last answer leaves a nearly empty final recording."""
    interview = await _interview_with_parts(db_session, join, parts=2)
    original = interview.interview.r2_key
    calls = []

    async def concat_that_chokes_on_the_final(recordings):
        calls.append(list(recordings))
        if b"FINAL" in recordings:
            raise RuntimeError("ffmpeg could not join the recordings")
        return b"+".join(recordings)

    monkeypatch.setattr(tasks_module, "concat_recordings", concat_that_chokes_on_the_final)

    merged = await _merge(db_session, interview)

    assert calls == [[b"P1", b"P2", b"FINAL"], [b"P1", b"P2"]]
    assert merged.r2_key == merge_key(interview.interview.id)
    assert join["storage"].files[merged.r2_key] == b"P1+P2"
    # The unusable final recording is deleted too, so nothing outlives the retention period.
    assert original in join["storage"].deleted
    assert (await _run(db_session, interview.interview)).recording_parts == 0


@pytest.mark.asyncio
async def test_a_failed_upload_of_the_joined_video_changes_nothing(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=1)
    original = interview.interview.r2_key
    join["storage"].fail_upload = True

    merged = await _merge(db_session, interview)

    assert merged.r2_key == original
    assert join["storage"].deleted == []
    assert (await _run(db_session, interview.interview)).recording_parts == 1


@pytest.mark.asyncio
async def test_joining_twice_joins_once(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=2)

    await _merge(db_session, interview)
    second = await _merge(db_session, interview)

    assert len(join["calls"]) == 1
    assert second.r2_key == merge_key(interview.interview.id)


@pytest.mark.asyncio
async def test_a_failed_join_can_be_run_again_and_then_succeeds(db_session, join):
    interview = await _interview_with_parts(db_session, join, parts=1)
    join["fail"] = True
    await _merge(db_session, interview)
    join["fail"] = False

    merged = await _merge(db_session, interview)

    assert merged.r2_key == merge_key(interview.interview.id)
    assert join["storage"].files[merge_key(interview.interview.id)] == b"P1+FINAL"
