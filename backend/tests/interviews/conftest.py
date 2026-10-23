"""Factory helpers shared across the interviews test suite.

These are plain async functions, not fixtures — same convention as the
top-level `tests/conftest.py` factories (`make_employer`, `make_job`, etc.).
The interviews module needs candidate/talent-pool/application/interview-list
setup that no existing shared factory covers, so it lives here rather than
being duplicated across `test_interview_service.py`, `test_interview_tasks.py`,
and `test_interview_router.py`.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import settings
from app.modules.applications.models import Application
from app.modules.candidates.models import CandidateProfile
from app.modules.interview_list.models import InterviewListEntry
from app.modules.interviews import strict as strict_module
from app.modules.interviews.models import Interview
from app.modules.interviews.service import InterviewService
from app.modules.interviews.strict import StrictInterviewService
from app.modules.talent_pool.models import TalentPoolProfiles
from tests.conftest import make_user


@pytest.fixture(autouse=True)
def _interview_is_twenty_minutes_long(monkeypatch):
    """The interview's length comes from INTERVIEW_MAX_DURATION_MINUTES in the developer's own
    .env (10, 3, whatever they are trying). The tests here are written for 20, so they must not
    depend on it; a test that cares about another length sets it itself."""
    monkeypatch.setattr(settings, "interview_max_duration_minutes", 20)


# What the fake speech-to-text hears unless a test queues something else.
LONG_ANSWER = "I designed the billing service so that every charge was recorded before it was sent."


class FakeSpeech:
    """Stands in for speech-to-text: hands back queued texts, or fails on demand."""

    def __init__(self):
        self.texts: list[str] = []
        self.calls = 0
        self.fail = False
        self.seconds = 60.0

    async def __call__(self, audio, filename):
        self.calls += 1
        if self.fail:
            raise RuntimeError("speech to text is down")
        return (self.texts.pop(0) if self.texts else LONG_ANSWER), self.seconds


class FakeAI:
    """Stands in for the follow-up model: hands back queued replies, or fails on demand."""

    def __init__(self):
        self.replies: list[str | None] = []
        self.calls: list[dict] = []
        self.fail = False

    async def decide_interview_follow_up(self, *, question, answer, interview_brief):
        self.calls.append({"question": question, "answer": answer, "brief": interview_brief})
        if self.fail:
            raise RuntimeError("the model is down")
        return self.replies.pop(0) if self.replies else None


@pytest.fixture
def fakes(monkeypatch):
    """The strict interview with its speech-to-text and follow-up model replaced (no API call)."""
    speech, ai = FakeSpeech(), FakeAI()
    monkeypatch.setattr(
        InterviewService,
        "_strict",
        lambda self: StrictInterviewService(self._db, self._repo, transcribe=speech, ai_service=ai),
    )
    return SimpleNamespace(speech=speech, ai=ai)


@pytest.fixture
def clock(monkeypatch):
    """The server's clock, starting now and moved by the test."""
    state = {"now": datetime.now(UTC)}
    monkeypatch.setattr(strict_module, "_now", lambda: state["now"])

    def advance(seconds):
        state["now"] += timedelta(seconds=seconds)

    return SimpleNamespace(advance=advance, now=lambda: state["now"])


@pytest.fixture(autouse=True)
def _interview_tests_never_reach_real_storage_or_openai(monkeypatch):
    """The transcript cross-check downloads the recording and calls Whisper. With
    it on, a task test whose interview has a recording key would reach the real
    storage service. Off for every interviews test; a test of the cross-check turns
    it on itself, with storage and OpenAI mocked."""
    monkeypatch.setattr(settings, "interview_transcript_crosscheck_enabled", False)


def make_candidate_user(**overrides) -> "object":
    """Build an unsaved CANDIDATE-role User instance."""
    return make_user(role="CANDIDATE", **overrides)


async def make_candidate_profile(db_session, user, **overrides) -> CandidateProfile:
    """Create and flush a CandidateProfile for an already-flushed candidate User."""
    defaults = {"user_id": user.id}
    defaults.update(overrides)
    profile = CandidateProfile(**defaults)
    db_session.add(profile)
    await db_session.flush()
    return profile


async def make_talent_pool_profile(
    db_session, added_by_id, candidate_profile_id=None, **overrides
) -> TalentPoolProfiles:
    """Create and flush a TalentPoolProfiles row.

    Sourced-only (no candidate_profile_id, no override_email) by default —
    pass `override_email=...` or `candidate_profile_id=...` for the cases
    where an email needs to be resolvable.
    """
    defaults = {
        "added_by": added_by_id,
        "candidate_profile_id": candidate_profile_id,
        "source": "OTHER",
    }
    defaults.update(overrides)
    profile = TalentPoolProfiles(**defaults)
    db_session.add(profile)
    await db_session.flush()
    return profile


async def make_application(db_session, candidate_id, job_id, **overrides) -> Application:
    """Create and flush an Application row."""
    defaults = {"candidate_id": candidate_id, "job_id": job_id}
    defaults.update(overrides)
    application = Application(**defaults)
    db_session.add(application)
    await db_session.flush()
    return application


async def make_interview_list_entry(
    db_session, employer_id, talent_pool_profile_id, job_id, **overrides
) -> InterviewListEntry:
    """Create and flush an InterviewListEntry — this is what 'invited' means."""
    defaults = {
        "employer_id": employer_id,
        "talent_pool_profile_id": talent_pool_profile_id,
        "job_id": job_id,
    }
    defaults.update(overrides)
    entry = InterviewListEntry(**defaults)
    db_session.add(entry)
    await db_session.flush()
    return entry


async def make_interview(db_session, job_id, talent_pool_profile_id, **overrides) -> Interview:
    """Create and flush an Interview row directly, bypassing InterviewService —
    for tests that need to seed pre-existing interview state."""
    defaults = {"job_id": job_id, "talent_pool_profile_id": talent_pool_profile_id}
    defaults.update(overrides)
    interview = Interview(**defaults)
    db_session.add(interview)
    await db_session.flush()
    return interview


def unique_token() -> str:
    """A short unique token string for tests that need one."""
    return uuid4().hex
