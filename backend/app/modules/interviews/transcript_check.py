"""Compare the transcript a candidate's browser submitted with the server's own
transcription of the recording.

The submitted transcript is typed into the scoring prompt, but it is assembled
on the candidate's device, so a candidate could submit text that was never said.
Two independent speech-to-text runs on the same audio agree closely even when
individual words differ, so we measure how many of the submitted transcript's
consecutive word pairs also appear in the server transcript. Pairs, not single
words, because a forged transcript padded with common words would still pass a
word-by-word comparison.
"""

import re
from collections import Counter
from dataclasses import dataclass

from app.modules.interviews.enums import TranscriptCheckStatus

# Speaker labels the browser adds ("AI: ...", "Candidate: ..."). They are not
# speech, so they are removed before comparing.
_LABEL_RE = re.compile(r"^(?:AI|Candidate):\s*", re.MULTILINE)
_WORD_RE = re.compile(r"[a-z0-9']+")

# Below this many words the submitted transcript says too little to judge.
MIN_SUBMITTED_WORDS = 30
# A recording with fewer words than this contains no real conversation.
MIN_SERVER_WORDS = 10


@dataclass(frozen=True)
class TranscriptCheckOutcome:
    """Result of comparing two transcripts of the same interview."""

    status: str
    match_score: float | None


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(_LABEL_RE.sub("", text).lower())


def _word_pairs(words: list[str]) -> Counter:
    return Counter(zip(words, words[1:], strict=False))


def compare_transcripts(
    submitted: str, server: str, threshold: float
) -> TranscriptCheckOutcome:
    """Decide whether the submitted transcript matches the recording.

    VERIFIED: enough of the submitted word pairs appear in the server transcript.
    MISMATCH: they clearly disagree, or the recording holds no speech at all
        while the submitted transcript claims a conversation.
    UNAVAILABLE: the submitted transcript is too short to judge.
    """
    submitted_words = _words(submitted)
    if len(submitted_words) < MIN_SUBMITTED_WORDS:
        return TranscriptCheckOutcome(TranscriptCheckStatus.UNAVAILABLE.value, None)

    server_words = _words(server)
    if len(server_words) < MIN_SERVER_WORDS:
        return TranscriptCheckOutcome(TranscriptCheckStatus.MISMATCH.value, 0.0)

    submitted_pairs = _word_pairs(submitted_words)
    shared = sum((submitted_pairs & _word_pairs(server_words)).values())
    match_score = round(shared / sum(submitted_pairs.values()), 4)

    status = (
        TranscriptCheckStatus.VERIFIED
        if match_score >= threshold
        else TranscriptCheckStatus.MISMATCH
    )
    return TranscriptCheckOutcome(status.value, match_score)
