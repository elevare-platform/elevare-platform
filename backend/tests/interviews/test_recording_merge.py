"""Joining the pieces of a strict interview's recording into one video, with real ffmpeg.

A page reload leaves the interview with more than one recording: what was recorded before the
reload, and what was recorded after. The employer must be able to play the interview from start
to finish as one file, whatever picture size and audio layout each piece happens to have."""

import asyncio
import json
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

from app.modules.interviews.recording_merge import (
    JoinTimedOut,
    build_command,
    can_copy,
    concat_recordings,
    merge_key,
    part_key,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg is not installed here",
)


def make_webm(seconds: float, *, size: str, channels: int = 1, frequency: int = 440) -> bytes:
    """A real, small WebM like the browser's recorder makes: video and audio."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "piece.webm"
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", f"testsrc=size={size}:rate=15:duration={seconds}",
                "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={seconds}",
                "-ac", str(channels),
                "-c:v", "libvpx", "-b:v", "200k", "-c:a", "libopus",
                str(out),
            ],
            check=True,
        )
        return out.read_bytes()


def probe(data: bytes) -> dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "in.webm"
        path.write_bytes(data)
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-count_packets",
                "-show_entries", "stream=codec_type,width,height,nb_read_packets:format=duration",
                "-of", "json", str(path),
            ],
            check=True, capture_output=True, text=True,
        )
    return json.loads(result.stdout)


def streams(info: dict) -> dict:
    return {stream["codec_type"]: stream for stream in info["streams"]}


@pytest.mark.asyncio
async def test_two_pieces_become_one_video_as_long_as_both_together():
    first = make_webm(2, size="320x240")
    second = make_webm(3, size="640x360", channels=2, frequency=880)

    joined = await concat_recordings([first, second])

    info = probe(joined)
    found = streams(info)
    assert set(found) == {"video", "audio"}
    assert float(info["format"]["duration"]) == pytest.approx(5.0, abs=0.6)
    # Both pieces, whatever their own size, come out at one picture size.
    assert (found["video"]["width"], found["video"]["height"]) == (1280, 720)


@pytest.mark.asyncio
async def test_pieces_from_one_browser_are_joined_by_copying_not_re_encoding():
    """Same codecs and size, as one browser and camera produce: joined losslessly and fast. The
    picture keeps its own size (a re-encode would have scaled it to 1280x720)."""
    first = make_webm(2, size="320x240")
    second = make_webm(3, size="320x240")

    started = time.monotonic()
    joined = await concat_recordings([first, second])
    took = time.monotonic() - started

    info = probe(joined)
    found = streams(info)
    assert (found["video"]["width"], found["video"]["height"]) == (320, 240)
    assert float(info["format"]["duration"]) == pytest.approx(5.0, abs=0.6)
    assert set(found) == {"video", "audio"}
    assert took < 5


@pytest.mark.asyncio
async def test_pieces_of_a_different_size_are_still_re_encoded_to_one_size():
    joined = await concat_recordings([make_webm(1, size="320x240"), make_webm(1, size="640x360")])

    found = streams(probe(joined))
    assert (found["video"]["width"], found["video"]["height"]) == (1280, 720)


@pytest.mark.asyncio
async def test_a_re_encoding_join_that_takes_too_long_is_stopped():
    """Different sizes need re-encoding, which is slow; scoring cannot wait for it."""
    with pytest.raises(JoinTimedOut):
        await concat_recordings(
            [make_webm(2, size="320x240"), make_webm(2, size="640x360")], reencode_timeout=0.01
        )


@pytest.mark.asyncio
async def test_a_join_by_copying_is_not_held_to_the_re_encoding_limit():
    joined = await concat_recordings(
        [make_webm(1, size="320x240"), make_webm(1, size="320x240")], reencode_timeout=0.01
    )

    assert float(probe(joined)["format"]["duration"]) > 0


@pytest.mark.asyncio
async def test_a_joined_recording_has_a_length_so_a_browser_can_seek_in_it():
    """A browser's own recording has no duration (it was never finished as a file); the joined
    one does."""
    joined = await concat_recordings([make_webm(2, size="320x240"), make_webm(2, size="320x240")])

    assert float(probe(joined)["format"]["duration"]) > 0


@pytest.mark.asyncio
async def test_a_browser_style_recording_without_a_length_is_joined_by_copying():
    """What the browser really makes: video and sound, but no duration in the file."""

    def without_length(data: bytes) -> bytes:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "in.webm"
            target = Path(tmpdir) / "out.webm"
            source.write_bytes(data)
            # Piping to a file in streaming mode leaves out the duration and the index.
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-c", "copy",
                 "-f", "webm", "-live", "1", str(target)],
                check=True,
            )
            return target.read_bytes()

    pieces = [without_length(make_webm(2, size="320x240")) for _ in range(2)]

    joined = await concat_recordings(pieces)

    assert float(probe(joined)["format"]["duration"]) == pytest.approx(4.0, abs=0.8)


def test_only_matching_pieces_may_be_copied():
    same = {"video": "vp9", "audio": "opus", "size": (640, 480), "duration": None}

    assert can_copy([same, dict(same)]) is True
    assert can_copy([same, {**same, "video": "vp8"}]) is False
    assert can_copy([same, {**same, "size": (1280, 720)}]) is False
    assert can_copy([same, {**same, "audio": "aac"}]) is False
    assert can_copy([same, None]) is False
    assert can_copy([]) is False


@pytest.mark.asyncio
async def test_three_pieces_after_two_reloads_keep_their_order_and_length():
    pieces = [make_webm(1, size="320x240"), make_webm(2, size="320x240"), make_webm(1, size="320x240")]

    joined = await concat_recordings(pieces)

    assert float(probe(joined)["format"]["duration"]) == pytest.approx(4.0, abs=0.7)


@pytest.mark.asyncio
async def test_a_single_piece_comes_out_as_a_playable_video_of_the_same_length():
    joined = await concat_recordings([make_webm(2, size="320x240")])

    assert float(probe(joined)["format"]["duration"]) == pytest.approx(2.0, abs=0.5)


@pytest.mark.asyncio
async def test_a_damaged_piece_is_reported_not_silently_dropped():
    with pytest.raises(RuntimeError, match="could not join"):
        await concat_recordings([make_webm(1, size="320x240"), b"this is not a video"])


@pytest.mark.asyncio
async def test_joining_nothing_is_a_mistake_in_the_caller():
    with pytest.raises(ValueError):
        await concat_recordings([])


def test_the_command_joins_in_the_order_given_and_limits_what_it_costs():
    paths = [Path("/tmp/a.webm"), Path("/tmp/b.webm")]

    command = build_command(paths, Path("/tmp/out.webm"))

    inputs = [command[i + 1] for i, word in enumerate(command) if word == "-i"]
    assert inputs == ["/tmp/a.webm", "/tmp/b.webm"]
    assert "concat=n=2:v=1:a=1" in command[command.index("-filter_complex") + 1]
    assert command[command.index("-threads") + 1] == "2"
    assert command[command.index("-deadline") + 1] == "realtime"


def test_each_piece_and_the_joined_video_have_their_own_storage_key():
    interview_id = uuid.uuid4()

    keys = {part_key(interview_id, 1), part_key(interview_id, 2), merge_key(interview_id)}

    assert len(keys) == 3
    assert all(key.startswith(f"interviews/{interview_id}/") and key.endswith(".webm") for key in keys)
    # Never the key the browser uploads the final recording to.
    assert merge_key(interview_id) != f"interviews/{interview_id}/recording.webm"


def test_the_event_loop_is_not_blocked_by_the_join():
    """The join runs ffmpeg as a subprocess, so other work on the worker keeps going."""
    async def run():
        ticks = 0

        async def tick():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        ticker = asyncio.create_task(tick())
        await concat_recordings([make_webm(1, size="320x240"), make_webm(1, size="320x240")])
        ticker.cancel()
        return ticks

    assert asyncio.run(run()) > 0
