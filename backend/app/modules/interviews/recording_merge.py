"""Join the pieces of one strict interview's recording into a single video.

A candidate whose page reloads in the middle of the interview keeps what was recorded so far in
their browser, and sends it as a separate part when they come back (docs/08_DECISIONS.md,
"The new strict, text-only AI interview", item 24). Each piece is a separate WebM file from a
separate recorder, with its own start and its own clock, so the bytes cannot simply be glued
together: they are joined here with ffmpeg into one file the employer can play from start to
finish. This runs in a worker task, not in a request. Pieces from one browser are joined by
copying their streams (a fraction of a second, and the result gets the duration and index a
browser's own recording lacks, so it can be sought); only pieces that differ in codec or size are
re-encoded, which takes about as long as the video itself.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

# Every piece is brought to this picture size and frame rate first, since the camera can
# change between a reload and the next start, and the join needs them equal.
_WIDTH, _HEIGHT, _FPS = 1280, 720, 30


def final_key(interview_id, attempt: int = 1) -> str:
    """Where the browser uploads the final recording of attempt ``attempt``. The first attempt
    keeps the name every interview has always used; a reinstated interview's later attempts
    get their own, so an earlier attempt's recording is never overwritten."""
    if attempt <= 1:
        return f"interviews/{interview_id}/recording.webm"
    return f"interviews/{interview_id}/recording-a{attempt}.webm"


def merge_key(interview_id, attempt: int = 1) -> str:
    """Where the joined recording of an attempt is stored. A different key from every piece
    (and from every other attempt's), so a task that stops half way and runs again can never
    read its own output as an input, and a later attempt never overwrites an earlier one."""
    if attempt <= 1:
        return f"interviews/{interview_id}/recording-merged.webm"
    return f"interviews/{interview_id}/recording-merged-a{attempt}.webm"


def part_key(interview_id, part: int) -> str:
    """Where part number ``part`` (1, 2, ...) of an interview's recording is uploaded."""
    return f"interviews/{interview_id}/part-{part}.webm"


def build_command(paths: list[Path], out_path: Path) -> list[str]:
    """The ffmpeg command that joins ``paths``, in order, into ``out_path``."""
    command = ["ffmpeg", "-y", "-loglevel", "error"]
    for path in paths:
        command += ["-i", str(path)]
    pieces = []
    for index in range(len(paths)):
        pieces.append(
            f"[{index}:v:0]fps={_FPS},scale={_WIDTH}:{_HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={_WIDTH}:{_HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{index}]"
        )
        pieces.append(
            f"[{index}:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{index}]"
        )
    joined = "".join(f"[v{i}][a{i}]" for i in range(len(paths)))
    pieces.append(f"{joined}concat=n={len(paths)}:v=1:a=1[v][a]")
    command += [
        "-filter_complex",
        ";".join(pieces),
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libvpx",
        "-b:v",
        "1500k",
        # Fast encoding and few threads: this runs inside a worker with a memory limit shared
        # with other tasks, and a recording of a few reloads does not need the best quality.
        "-deadline",
        "realtime",
        "-cpu-used",
        "8",
        "-threads",
        "2",
        "-c:a",
        "libopus",
        "-b:a",
        "64k",
        str(out_path),
    ]
    return command


class JoinTimedOut(Exception):
    """The re-encoding join was stopped for taking longer than it was allowed. Not a
    RuntimeError on purpose: that means "these pieces will not join", and trying again with
    fewer pieces would only be slow again."""


async def _run(command: list[str], timeout: float | None = None) -> tuple[int, bytes, bytes]:
    process = await asyncio.create_subprocess_exec(
        *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(process.communicate(), timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise JoinTimedOut(f"ffmpeg ran for more than {timeout} seconds") from None
    return process.returncode, out, err


async def probe(path: Path) -> dict | None:
    """What ffprobe says about a recording: its video and audio codecs, the picture size and
    the duration (None when the file has no duration, as a browser's recording often has not).
    None when the file cannot be read or lacks the video or the audio."""
    code, out, _ = await _run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "stream=codec_type,codec_name,width,height:format=duration",
            "-of", "json", str(path),
        ]
    )
    if code != 0:
        return None
    try:
        info = json.loads(out or b"{}")
    except ValueError:
        return None
    streams = {s.get("codec_type"): s for s in info.get("streams", [])}
    if "video" not in streams or "audio" not in streams:
        return None
    try:
        duration = float(info.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        duration = None
    return {
        "video": streams["video"].get("codec_name"),
        "audio": streams["audio"].get("codec_name"),
        "size": (streams["video"].get("width"), streams["video"].get("height")),
        "duration": duration,
    }


def can_copy(signatures: list[dict | None]) -> bool:
    """Whether the pieces can be joined without re-encoding: every one readable, with the same
    codecs and the same picture size, which is what one browser and camera produce."""
    if not signatures or any(s is None for s in signatures):
        return False
    first = signatures[0]
    return all(
        (s["video"], s["audio"], s["size"]) == (first["video"], first["audio"], first["size"])
        for s in signatures
    )


async def _join_by_copy(paths: list[Path], out_path: Path) -> bool:
    """Join by copying the streams: about a third of a second, however long, and it writes the
    duration and the index a browser's own recording lacks, so the video can be sought. True
    when it worked and the result has a picture, a sound and a length."""
    listing = out_path.parent / "pieces.txt"
    listing.write_text("".join(f"file '{path}'\n" for path in paths))
    code, _, _ = await _run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(out_path)]
    )
    if code != 0:
        return False
    result = await probe(out_path)
    return bool(result and result["duration"])


async def concat_recordings(recordings: list[bytes], reencode_timeout: float | None = None) -> bytes:
    """Join WebM recordings, in the order given, into one WebM.

    Pieces from one browser share their codecs and size, so they are joined by copying the
    streams, which takes a fraction of a second. Anything else (a different browser, another
    camera) is re-encoded to one size, which is slow (about the length of the video) but always
    works. Raises RuntimeError when ffmpeg cannot join them (a damaged piece, say), and
    JoinTimedOut when the re-encoding takes longer than ``reencode_timeout`` seconds (no limit
    when None); the caller decides what to do about either."""
    if not recordings:
        raise ValueError("nothing to join")
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for index, data in enumerate(recordings):
            path = Path(tmpdir) / f"part{index}.webm"
            path.write_bytes(data)
            paths.append(path)
        out_path = Path(tmpdir) / "merged.webm"

        if can_copy([await probe(path) for path in paths]) and await _join_by_copy(paths, out_path):
            return out_path.read_bytes()

        code, _, stderr = await _run(build_command(paths, out_path), reencode_timeout)
        if code != 0:
            raise RuntimeError(
                f"ffmpeg could not join the recordings (exit {code}): "
                f"{stderr.decode(errors='replace')[-2000:]}"
            )
        return out_path.read_bytes()
