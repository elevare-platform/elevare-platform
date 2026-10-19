"""What the client sees on the shared results page."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.ai.models import ParsedCVSubmission
from app.modules.interview_share import service as share_service_module
from app.modules.interview_share.service import InterviewShareService
from app.modules.interviews.models import InterviewTranscriptCheck
from tests.conftest import make_employer, make_job, make_organization_for
from tests.interviews.conftest import (
    make_candidate_profile,
    make_candidate_user,
    make_interview,
    make_interview_list_entry,
    make_talent_pool_profile,
)

TRANSCRIPT = (
    "AI: Welcome. Tell me about managing distributors?\n\n"
    "Candidate: I grew the network from twelve to forty.\n\n"
    "AI: Good. What was the hardest part? And how did you handle it?\n\n"
    "Candidate: Credit control."
)
ASSESSMENT = "A confident communicator.\n\nStrengths:\n- Clear examples\n\nWeaknesses:\n- Light on numbers"


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    """A recording link that is short-lived, without touching real storage."""
    from app.modules.interviews import service as interview_service_module

    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/video")
    monkeypatch.setattr(interview_service_module, "get_storage_service", lambda: fake)
    return fake


async def setup_job(db_session, *, brief="Probe distributor management."):
    employer = make_employer()
    db_session.add(employer)
    await db_session.flush()
    organization = await make_organization_for(db_session, employer)
    organization.company_name = "Colton Group"
    job = make_job(employer.id, interview_brief=brief)
    db_session.add(job)
    await db_session.flush()
    return employer, job


async def sourced(db_session, employer, name, **interview):
    """A sourced candidate on the job's interview list, optionally with an interview."""
    submission = ParsedCVSubmission(
        filename="cv.pdf",
        parse_status="completed",
        parsed_data={"full_name": name, "current_title": "Sales Manager", "skills": ["Excel"]},
    )
    db_session.add(submission)
    await db_session.flush()
    profile = await make_talent_pool_profile(
        db_session, employer.id, parsed_submission_id=submission.id
    )
    return profile


async def add_to_list(db_session, employer, job, profile, **interview):
    await make_interview_list_entry(db_session, employer.id, profile.id, job.id)
    if interview:
        return await make_interview(db_session, job.id, profile.id, **interview)
    return None


def completed(**overrides):
    return {
        "status": "SCORED",
        "ai_score": 82,
        "ai_rationale": ASSESSMENT,
        "transcript": TRANSCRIPT,
        "r2_key": "interviews/one.webm",
        "completed_at": datetime(2026, 10, 20, 9, 0, tzinfo=UTC),
        **overrides,
    }


async def results(db_session, employer, job):
    service = InterviewShareService(db_session)
    link = await service.create(employer, job.id)
    return await service.get_results(link.url.rsplit("/", 1)[1])


# --- the page as a whole ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_page_names_the_job_the_company_and_what_the_ai_was_told_to_cover(db_session):
    employer, job = await setup_job(db_session)

    page = await results(db_session, employer, job)

    assert page.job_title == job.title
    assert page.company_name == "Colton Group"
    assert page.interview_focus == "Probe distributor management."
    assert page.candidates == []


@pytest.mark.asyncio
async def test_only_candidates_on_this_jobs_interview_list_are_shown(db_session):
    employer, job = await setup_job(db_session)
    other_job = make_job(employer.id)
    db_session.add(other_job)
    await db_session.flush()
    on_list = await sourced(db_session, employer, "Ada Obi")
    elsewhere = await sourced(db_session, employer, "Chidi Okafor")
    await add_to_list(db_session, employer, job, on_list)
    await add_to_list(db_session, employer, other_job, elsewhere)

    page = await results(db_session, employer, job)

    assert [c.name for c in page.candidates] == ["Ada Obi"]


# --- a completed interview -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_completed_interview_shows_the_score_the_ai_assessment_and_the_recording(
    db_session,
):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    await add_to_list(db_session, employer, job, profile, **completed())

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.name == "Ada Obi"
    assert candidate.status == "COMPLETED"
    assert candidate.interview_score == 82
    assert candidate.interview_assessment == ASSESSMENT
    assert candidate.video_url == "https://signed.example/video"
    assert candidate.completed_at == datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


@pytest.mark.asyncio
async def test_the_ais_questions_are_listed_one_by_one_and_the_conversation_is_split_into_turns(
    db_session,
):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    await add_to_list(db_session, employer, job, profile, **completed())

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.questions == [
        "Tell me about managing distributors?",
        "What was the hardest part?",
        "And how did you handle it?",
    ]
    assert [(t.speaker, t.text[:12]) for t in candidate.turns] == [
        ("AI", "Welcome. Tel"),
        ("Candidate", "I grew the n"),
        ("AI", "Good. What w"),
        ("Candidate", "Credit contr"),
    ]
    assert candidate.transcript is None  # the turns are the transcript


@pytest.mark.asyncio
async def test_the_recording_link_is_short_lived(db_session, storage):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    await add_to_list(db_session, employer, job, profile, **completed())

    await results(db_session, employer, job)

    seconds = storage.generate_presigned_url.await_args.kwargs["expires_seconds"]
    assert seconds == share_service_module.VIDEO_LINK_SECONDS == 15 * 60


@pytest.mark.asyncio
async def test_a_transcript_without_speaker_labels_is_shown_as_plain_text(db_session):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    await add_to_list(
        db_session, employer, job, profile, **completed(transcript="Just the words, no labels.")
    )

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.turns == [] and candidate.questions == []
    assert candidate.transcript == "Just the words, no labels."


@pytest.mark.asyncio
async def test_a_transcript_that_did_not_match_the_recording_says_so(db_session):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    interview = await add_to_list(db_session, employer, job, profile, **completed())
    db_session.add(
        InterviewTranscriptCheck(
            interview_id=interview.id,
            status="MISMATCH",
            server_transcript="What the recording itself says.",
        )
    )
    await db_session.flush()

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.transcript == "What the recording itself says."
    assert "no speaker labels" in candidate.transcript_note


# --- the CV assessment beside it -------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_cv_assessment_is_shown_beside_the_interview_assessment(db_session):
    from app.modules.ai.scoring_service import hash_job_scoring_inputs
    from app.modules.jobs.schemas import build_full_description

    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    description = build_full_description(
        about_the_role=job.about_the_role,
        key_responsibilities=job.key_responsibilities,
        requirements=job.requirements,
        preferred_certifications=job.preferred_certifications,
        technical_competencies=job.technical_competencies,
        what_we_offer=job.what_we_offer,
        legacy_description=job.description,
    )
    profile.ai_score = 74
    profile.ai_fit_summary = "Strong sales background."
    profile.ai_strengths = ["Distributor growth"]
    profile.ai_weaknesses = ["No FMCG"]
    profile.ai_score_job_hash = hash_job_scoring_inputs(
        description, job.required_skills or [], job.seniority_level
    )
    await db_session.flush()
    await add_to_list(db_session, employer, job, profile, **completed())

    [candidate] = (await results(db_session, employer, job)).candidates

    assert (candidate.cv_score, candidate.cv_summary) == (74, "Strong sales background.")
    assert candidate.cv_strengths == ["Distributor growth"]
    assert candidate.cv_weaknesses == ["No FMCG"]


@pytest.mark.asyncio
async def test_a_cv_score_that_was_made_for_a_different_job_is_not_shown(db_session):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    profile.ai_score = 91
    profile.ai_fit_summary = "Scored for some other job."
    profile.ai_score_job_hash = "hash-of-a-different-job"
    await db_session.flush()
    await add_to_list(db_session, employer, job, profile, **completed())

    [candidate] = (await results(db_session, employer, job)).candidates

    assert (candidate.cv_score, candidate.cv_summary) == (None, None)


# --- candidates who have not interviewed ----------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("interview_status", "expected"),
    [
        (None, "NOT_INVITED"),
        ("PENDING", "INVITED"),
        ("IN_PROGRESS", "IN_PROGRESS"),
        ("FAILED", "NOT_COMPLETED"),
        ("EXPIRED", "NOT_COMPLETED"),
        ("UPLOADED", "COMPLETED"),
        ("SCORED", "COMPLETED"),
    ],
)
async def test_each_interview_state_has_a_plain_status(db_session, interview_status, expected):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    extra = {"status": interview_status} if interview_status else {}
    await add_to_list(db_session, employer, job, profile, **extra)

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.status == expected


@pytest.mark.asyncio
async def test_a_candidate_who_has_not_interviewed_has_no_recording_or_transcript(db_session):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    await add_to_list(db_session, employer, job, profile, status="PENDING", transcript="never shown")

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.video_url is None
    assert candidate.questions == [] and candidate.turns == []
    assert candidate.transcript is None
    assert candidate.interview_score is None


@pytest.mark.asyncio
async def test_a_name_the_candidate_has_not_shared_stays_masked_until_they_interview(db_session):
    employer, job = await setup_job(db_session)
    user = make_candidate_user()
    db_session.add(user)
    await db_session.flush()
    candidate_profile = await make_candidate_profile(db_session, user, visibility="PRIVATE")
    profile = await make_talent_pool_profile(
        db_session, employer.id, candidate_profile_id=candidate_profile.id
    )
    await add_to_list(db_session, employer, job, profile)  # on the list, not interviewed

    [before] = (await results(db_session, employer, job)).candidates
    assert before.name == "Candidate 1"

    await make_interview(db_session, job.id, profile.id, **completed())
    [after] = (await results(db_session, employer, job)).candidates
    assert after.name == f"{user.first_name} {user.last_name}".strip()


# --- order and size ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completed_interviews_come_first_best_score_first_then_by_progress(db_session):
    employer, job = await setup_job(db_session)
    plan = [
        ("Not Invited", {}),
        ("Invited", {"status": "PENDING"}),
        ("Low Score", completed(ai_score=40)),
        ("High Score", completed(ai_score=90)),
        ("In Progress", {"status": "IN_PROGRESS"}),
    ]
    for name, interview in plan:
        profile = await sourced(db_session, employer, name)
        await add_to_list(db_session, employer, job, profile, **interview)

    page = await results(db_session, employer, job)

    assert [c.name for c in page.candidates] == [
        "High Score",
        "Low Score",
        "In Progress",
        "Invited",
        "Not Invited",
    ]
    assert (page.total_candidates, page.completed_count) == (5, 2)


@pytest.mark.asyncio
async def test_a_very_long_list_is_cut_and_the_page_says_so(db_session, monkeypatch):
    monkeypatch.setattr(share_service_module, "MAX_CANDIDATES", 2)
    employer, job = await setup_job(db_session)
    for name in ("One", "Two", "Three"):
        await add_to_list(db_session, employer, job, await sourced(db_session, employer, name))

    page = await results(db_session, employer, job)

    assert len(page.candidates) == 2
    assert page.truncated is True
    assert page.total_candidates == 3
