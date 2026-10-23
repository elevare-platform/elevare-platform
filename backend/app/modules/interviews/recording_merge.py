"""Join the pieces of one strict interview's recording into a single video.

A candidate whose page reloads in the middle of the interview keeps what was recorded so far in
their browser, and sends it as a separate part when they come back (docs/08_DECISIONS.md,
"The new strict, text-only AI interview", item 24). Each piece is a separate WebM file from a
separate recorder, with its own start and its own clock, so the bytes cannot simply be glued
together: they are joined here with ffmpeg into one file the employer can play from start to
finish. This runs in the scoring task, not in a request, because re-encoding takes a while.
"""

from __future__ import annotations

import asyncio
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


async def concat_recordings(recordings: list[bytes]) -> bytes:
    """Join WebM recordings, in the order given, into one WebM. Raises RuntimeError when
    ffmpeg cannot (a damaged piece, say); the caller decides what to do about it."""
    if not recordings:
        raise ValueError("nothing to join")
    with tempfile.TemporaryDirectory() as tmpdir:
        paths = []
        for index, data in enumerate(recordings):
            path = Path(tmpdir) / f"part{index}.webm"
            path.write_bytes(data)
            paths.append(path)
        out_path = Path(tmpdir) / "merged.webm"
        process = await asyncio.create_subprocess_exec(
            *build_command(paths, out_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"ffmpeg could not join the recordings (exit {process.returncode}): "
                f"{stderr.decode(errors='replace')[-2000:]}"
            )
        return out_path.read_bytes()
