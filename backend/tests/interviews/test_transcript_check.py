"""Tests for comparing a candidate-device transcript with the recording's own."""

from app.modules.interviews.enums import TranscriptCheckStatus
from app.modules.interviews.transcript_check import compare_transcripts

THRESHOLD = 0.40

_REAL = (
    "AI: Thanks for joining. Can you walk me through a system you scaled recently?\n\n"
    "Candidate: Sure. At my last company we ran a payments service on a single "
    "database and it started to struggle during peak hours. I introduced read "
    "replicas first, then moved the heaviest reports to a separate warehouse, "
    "and finally added a queue so that slow work no longer blocked checkout.\n\n"
    "AI: What was the hardest part of that change?\n\n"
    "Candidate: Convincing the team to accept eventual consistency for reports. "
    "I ran a two week pilot, showed them the latency numbers, and we agreed on "
    "a five minute freshness target that nobody noticed in practice."
)


def _noisy(text: str, every: int) -> str:
    """Simulate speech-to-text errors: replace every Nth word."""
    words = text.split()
    return " ".join("zzz" if i % every == 0 else w for i, w in enumerate(words, 1))


def _without_labels(text: str) -> str:
    return text.replace("AI: ", "").replace("Candidate: ", "")


def test_identical_transcripts_are_verified():
    outcome = compare_transcripts(_REAL, _without_labels(_REAL), THRESHOLD)

    assert outcome.status == TranscriptCheckStatus.VERIFIED.value
    assert outcome.match_score == 1.0


def test_normal_transcription_noise_is_still_verified():
    # One word in seven wrong is far noisier than two good engines disagree.
    outcome = compare_transcripts(_REAL, _noisy(_without_labels(_REAL), 7), THRESHOLD)

    assert outcome.status == TranscriptCheckStatus.VERIFIED.value
    assert outcome.match_score >= THRESHOLD


def test_speaker_labels_are_not_counted_as_speech():
    labelled = compare_transcripts(_REAL, _without_labels(_REAL), THRESHOLD)
    relabelled = compare_transcripts(
        _without_labels(_REAL), _without_labels(_REAL), THRESHOLD
    )

    assert labelled.match_score == relabelled.match_score == 1.0


def test_forged_transcript_is_a_mismatch():
    forged = (
        "Candidate: I led a team of fifty engineers and rebuilt the entire "
        "platform from scratch in three months, cutting our cloud costs by "
        "ninety percent while also winning an industry award for innovation "
        "and mentoring dozens of junior developers into senior roles across "
        "four different continents without a single production outage."
    )

    outcome = compare_transcripts(forged, _without_labels(_REAL), THRESHOLD)

    assert outcome.status == TranscriptCheckStatus.MISMATCH.value
    assert outcome.match_score < 0.1


def test_padding_a_forgery_with_common_words_does_not_pass():
    """Single-word overlap would let this through; word pairs do not."""
    padded = "Candidate: " + " ".join(["the and of to a in is that it for"] * 12)

    outcome = compare_transcripts(padded, _without_labels(_REAL), THRESHOLD)

    assert outcome.status == TranscriptCheckStatus.MISMATCH.value


def test_recording_with_no_speech_is_a_mismatch_for_a_claimed_conversation():
    outcome = compare_transcripts(_REAL, "", THRESHOLD)

    assert outcome.status == TranscriptCheckStatus.MISMATCH.value
    assert outcome.match_score == 0.0


def test_too_short_submitted_transcript_cannot_be_judged():
    outcome = compare_transcripts("AI: Hi\n\nCandidate: Hello", "hi hello", THRESHOLD)

    assert outcome.status == TranscriptCheckStatus.UNAVAILABLE.value
    assert outcome.match_score is None
