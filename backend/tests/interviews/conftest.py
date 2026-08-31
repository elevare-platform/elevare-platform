"""Factory helpers shared across the interviews test suite.

These are plain async functions, not fixtures — same convention as the
top-level `tests/conftest.py` factories (`make_employer`, `make_job`, etc.).
The interviews module needs candidate/talent-pool/application/interview-list
setup that no existing shared factory covers, so it lives here rather than
being duplicated across `test_interview_service.py`, `test_interview_tasks.py`,
and `test_interview_router.py`.
"""

from uuid import uuid4

from app.modules.applications.models import Application
from app.modules.candidates.models import CandidateProfile
from app.modules.interview_list.models import InterviewListEntry
from app.modules.interviews.models import Interview
from app.modules.talent_pool.models import TalentPoolProfiles
from tests.conftest import make_user


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
