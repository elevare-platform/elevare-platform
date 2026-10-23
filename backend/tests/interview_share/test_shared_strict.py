"""What the client sees on the shared results page for a strict interview, and for one that ended
early: the rules the candidate accepted, the conduct notes, how it ended, and each answer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.interviews.models import InterviewTurn, StrictInterviewRun

from .test_shared_results import add_to_list, results, setup_job, sourced


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    """A recording link that is short-lived, without touching real storage."""
    from app.modules.interviews import service as interview_service_module

    fake = MagicMock()
    fake.generate_presigned_url = AsyncMock(return_value="https://signed.example/video")
    monkeypatch.setattr(interview_service_module, "get_storage_service", lambda: fake)
    return fake

ACCEPTED = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)


async def strict_candidate(db_session, employer, job, name, **interview):
    profile = await sourced(db_session, employer, name)
    row = await add_to_list(
        db_session, employer, job, profile,
        r2_key="interviews/one.webm",
        completed_at=datetime(2026, 10, 20, 9, 30, tzinfo=UTC),
        **interview,
    )
    run = StrictInterviewRun(
        interview_id=row.id, rules_version="S2", rules_accepted_at=ACCEPTED,
        started_at=ACCEPTED, attempt=1,
    )
    db_session.add(run)
    db_session.add(
        InterviewTurn(
            interview_id=row.id, position=1, kind="QUESTION", question_number=1,
            question_text="Tell us about a system you designed.", time_limit_seconds=120,
            opened_at=ACCEPTED, answered_at=ACCEPTED, answer_text="I built the billing service.",
        )
    )
    await db_session.flush()
    return row, run


@pytest.mark.asyncio
async def test_an_interview_that_ended_early_shows_as_ended_with_its_notes_and_recording(db_session):
    employer, job = await setup_job(db_session)
    row, run = await strict_candidate(
        db_session, employer, job, "Ada Obi", status="ENDED_CONDUCT",
        transcript="AI: Tell us about a system you designed.\n\nCandidate: I built the billing service.",
    )
    run.end_reason = "TOO_MANY_LEAVES"
    run.ended_at = ACCEPTED
    await db_session.flush()

    page = await results(db_session, employer, job)

    [candidate] = page.candidates
    assert candidate.status == "ENDED"
    assert candidate.video_url == "https://signed.example/video"
    assert candidate.strict.ended == "TOO_MANY_LEAVES"
    assert candidate.strict.rules_version == "S2" and candidate.strict.rules_accepted_at == ACCEPTED
    assert candidate.strict.turns[0].answer == "I built the billing service."
    assert candidate.interview_score is None
    # An ended interview is not a completed one.
    assert page.completed_count == 0


@pytest.mark.asyncio
async def test_a_stopped_interview_also_shows_as_ended_and_says_the_candidate_chose_to(db_session):
    employer, job = await setup_job(db_session)
    row, run = await strict_candidate(db_session, employer, job, "Ada Obi", status="STOPPED")
    run.end_reason = "STOPPED"
    run.ended_at = ACCEPTED
    await db_session.flush()

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.status == "ENDED" and candidate.strict.ended == "STOPPED"


@pytest.mark.asyncio
async def test_a_finished_strict_interview_shows_its_rules_record_and_conduct_summary(db_session):
    employer, job = await setup_job(db_session)
    await strict_candidate(
        db_session, employer, job, "Ada Obi", status="SCORED", ai_score=80,
        ai_rationale="Clear.", transcript="AI: q\n\nCandidate: a",
    )

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.status == "COMPLETED" and candidate.interview_score == 80
    assert candidate.strict.rules_version == "S2" and candidate.strict.ended is None
    assert (candidate.strict.leaves, candidate.strict.away_seconds, candidate.strict.key_presses) == (0, 0, 0)


@pytest.mark.asyncio
async def test_a_live_interview_has_no_strict_block_on_the_shared_page(db_session):
    employer, job = await setup_job(db_session)
    profile = await sourced(db_session, employer, "Ada Obi")
    await add_to_list(
        db_session, employer, job, profile, status="SCORED", ai_score=70,
        ai_rationale="Fine.", transcript="AI: q\n\nCandidate: a",
        r2_key="interviews/one.webm", completed_at=ACCEPTED,
    )

    [candidate] = (await results(db_session, employer, job)).candidates

    assert candidate.strict is None


@pytest.mark.asyncio
async def test_completed_interviews_come_first_then_ended_ones(db_session):
    employer, job = await setup_job(db_session)
    ended, run = await strict_candidate(db_session, employer, job, "Bola Ade", status="STOPPED")
    run.end_reason = "STOPPED"
    run.ended_at = ACCEPTED
    await strict_candidate(
        db_session, employer, job, "Ada Obi", status="SCORED", ai_score=80,
        ai_rationale="Clear.", transcript="AI: q\n\nCandidate: a",
    )
    waiting = await sourced(db_session, employer, "Chidi Okafor")
    await add_to_list(db_session, employer, job, waiting, status="PENDING")
    await db_session.flush()

    page = await results(db_session, employer, job)

    assert [c.status for c in page.candidates] == ["COMPLETED", "ENDED", "INVITED"]
