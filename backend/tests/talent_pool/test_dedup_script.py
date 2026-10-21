"""The script that merges duplicate talent pool profiles already in the database.

It must never delete, never merge across people, never merge unrelated CVs that share the old
empty-text hash, and never lose an interview, an introduction, a saved candidate or a cost."""

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.modules.ai.models import FitScoringCost, ParsedCVSubmission
from app.modules.interview_list.models import InterviewListEntry
from app.modules.saved_candidates.models import SavedCandidate
from app.modules.talent_pool.models import TalentPoolProfiles
from scripts import dedup_talent_pool as script
from tests.conftest import make_employer, make_job
from tests.interviews.conftest import make_interview, make_talent_pool_profile

EMPTY = "empty-text-hash"
NOW = datetime(2026, 10, 20, tzinfo=UTC)


def profile(**overrides) -> dict:
    """A profile row as the script reads it."""
    row = {
        "id": uuid.uuid4(),
        "added_by": "owner-1",
        "sourced_for_job_id": None,
        "status": "new",
        "created_at": NOW,
        "candidate_profile_id": None,
        "promoted_application_id": None,
        "ai_score": None,
        "cv_text_hash": "cv-1",
    }
    row.update(overrides)
    return row


def plan(*profiles, children=None):
    return script.plan_merges(list(profiles), children or Counter(), EMPTY)


# --- what counts as a duplicate -----------------------------------------------------------


def test_the_same_cv_for_the_same_job_is_one_set():
    a, b = profile(sourced_for_job_id="job-1"), profile(sourced_for_job_id="job-1")

    [merge] = plan(a, b)

    assert {merge.keeper["id"], merge.losers[0]["id"]} == {a["id"], b["id"]}
    assert merge.skip is None and "same job" in merge.reason


def test_the_same_cv_with_no_job_twice_is_one_set():
    [merge] = plan(profile(), profile())

    assert "no job" in merge.reason


def test_a_copy_with_no_job_is_merged_into_the_one_profile_for_a_job():
    with_job, without = profile(sourced_for_job_id="job-1"), profile()

    [merge] = plan(with_job, without)

    assert merge.keeper["id"] == with_job["id"]  # whichever is older or better ranked
    assert [loser["id"] for loser in merge.losers] == [without["id"]]


def test_two_different_jobs_are_kept_apart_and_the_copy_with_no_job_is_left_alone():
    """A profile holds one score, so one per job is right; with two jobs it is unclear which
    one the copy with no job belongs to."""
    assert plan(profile(sourced_for_job_id="job-1"), profile(sourced_for_job_id="job-2"), profile()) == []


def test_two_people_with_the_same_cv_are_never_merged():
    assert plan(profile(added_by="owner-1"), profile(added_by="owner-2")) == []


def test_different_cvs_are_not_merged():
    assert plan(profile(cv_text_hash="cv-1"), profile(cv_text_hash="cv-2")) == []


def test_profiles_with_the_old_empty_text_hash_are_left_alone():
    """Every file with no readable text used to get this hash: they are unrelated people."""
    assert plan(profile(cv_text_hash=EMPTY), profile(cv_text_hash=EMPTY)) == []


def test_a_profile_with_no_hash_is_ignored():
    assert plan(profile(cv_text_hash=None), profile(cv_text_hash=None)) == []


# --- which one is kept ----------------------------------------------------------------------


def test_the_profile_tied_to_an_application_is_kept():
    promoted = profile(promoted_application_id=uuid.uuid4(), created_at=NOW + timedelta(days=5))
    older = profile(created_at=NOW)

    [merge] = plan(older, promoted)

    assert merge.keeper["id"] == promoted["id"] and merge.skip is None


def test_then_the_one_with_a_score_then_the_one_with_most_work_attached_then_the_oldest():
    scored = profile(ai_score=70, created_at=NOW + timedelta(days=9))
    busy, quiet = profile(created_at=NOW + timedelta(days=3)), profile(created_at=NOW + timedelta(days=2))
    oldest = profile(created_at=NOW)

    assert plan(oldest, scored)[0].keeper["id"] == scored["id"]
    assert plan(oldest, busy, quiet, children=Counter({busy["id"]: 4}))[0].keeper["id"] == busy["id"]
    assert plan(quiet, oldest)[0].keeper["id"] == oldest["id"]


def test_two_profiles_tied_to_different_applications_are_left_for_a_person():
    [merge] = plan(
        profile(promoted_application_id=uuid.uuid4()), profile(promoted_application_id=uuid.uuid4())
    )

    assert merge.skip and "promoted" in merge.skip


def test_two_profiles_of_self_registered_candidates_are_left_for_a_person():
    [merge] = plan(profile(candidate_profile_id=uuid.uuid4()), profile(candidate_profile_id=uuid.uuid4()))

    assert merge.skip


def test_a_copy_with_no_job_that_is_tied_to_a_candidate_is_not_merged_away():
    [merge] = plan(
        profile(sourced_for_job_id="job-1"), profile(candidate_profile_id=uuid.uuid4())
    )

    assert merge.skip and "bound" in merge.skip


# --- the merge itself (real database) -------------------------------------------------------


async def make_pair(db_session):
    """Two profiles for the same CV in one employer's pool, with a job on the second."""
    owner = make_employer()
    db_session.add(owner)
    await db_session.flush()
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()
    keeper = await make_talent_pool_profile(db_session, owner.id, status="new")
    loser = await make_talent_pool_profile(
        db_session, owner.id, status="new", sourced_for_job_id=job.id, source_note="mail import"
    )
    return owner, job, keeper, loser


def as_row(p: TalentPoolProfiles) -> dict:
    return {
        "id": p.id, "added_by": p.added_by, "sourced_for_job_id": p.sourced_for_job_id,
        "candidate_profile_id": p.candidate_profile_id, "promoted_application_id": None, "ai_score": None,
        "created_at": p.created_at, "status": p.status, "cv_text_hash": "x",
    }


@pytest.mark.asyncio
async def test_everything_pointing_at_the_copy_moves_to_the_kept_profile_and_nothing_is_deleted(db_session):
    owner, job, keeper, loser = await make_pair(db_session)
    other_employer = make_employer()
    db_session.add(other_employer)
    await db_session.flush()
    db_session.add_all([
        SavedCandidate(employer_id=owner.id, talent_pool_profile_id=loser.id),
        SavedCandidate(employer_id=other_employer.id, talent_pool_profile_id=loser.id),
        InterviewListEntry(employer_id=owner.id, talent_pool_profile_id=loser.id, job_id=job.id),
        FitScoringCost(talent_pool_profile_id=loser.id, job_id=job.id, input_tokens=10, output_tokens=5, model="m"),
    ])
    await db_session.flush()
    merge = script.Merge(as_row(keeper), [as_row(loser)], "test")

    await script.merge_one(db_session, merge)
    await db_session.flush()

    saved = (await db_session.execute(select(SavedCandidate).where(SavedCandidate.talent_pool_profile_id == keeper.id))).scalars().all()
    assert {s.employer_id for s in saved} == {owner.id, other_employer.id}
    assert (await db_session.execute(select(InterviewListEntry).where(InterviewListEntry.talent_pool_profile_id == keeper.id))).scalars().one().job_id == job.id
    assert (await db_session.execute(select(FitScoringCost).where(FitScoringCost.talent_pool_profile_id == keeper.id))).scalars().one().input_tokens == 10
    assert (await db_session.execute(select(SavedCandidate).where(SavedCandidate.talent_pool_profile_id == loser.id))).first() is None
    assert merge.moved["saved_candidates"] == 2 and merge.moved["fit_scoring_costs"] == 1


@pytest.mark.asyncio
async def test_the_copy_is_archived_with_a_note_not_deleted(db_session):
    _, _, keeper, loser = await make_pair(db_session)

    await script.merge_one(db_session, script.Merge(as_row(keeper), [as_row(loser)], "test"))
    await db_session.refresh(loser)

    assert loser.status == "archived"
    assert f"merged into {keeper.id}" in loser.source_note and loser.source_note.startswith("mail import")
    assert await db_session.get(TalentPoolProfiles, loser.id) is not None


@pytest.mark.asyncio
async def test_the_kept_profile_takes_the_job_when_it_had_none(db_session):
    _, job, keeper, loser = await make_pair(db_session)

    await script.merge_one(db_session, script.Merge(as_row(keeper), [as_row(loser)], "test"))
    await db_session.refresh(keeper)

    assert keeper.sourced_for_job_id == job.id


@pytest.mark.asyncio
async def test_a_row_the_kept_profile_already_has_is_not_duplicated(db_session):
    """The same employer saved both copies: one saved row is enough. (The unique rules would
    refuse a second one anyway.)"""
    owner, job, keeper, loser = await make_pair(db_session)
    db_session.add_all([
        SavedCandidate(employer_id=owner.id, talent_pool_profile_id=keeper.id),
        SavedCandidate(employer_id=owner.id, talent_pool_profile_id=loser.id),
        InterviewListEntry(employer_id=owner.id, talent_pool_profile_id=keeper.id, job_id=job.id),
        InterviewListEntry(employer_id=owner.id, talent_pool_profile_id=loser.id, job_id=job.id),
    ])
    await db_session.flush()
    merge = script.Merge(as_row(keeper), [as_row(loser)], "test")

    await script.merge_one(db_session, merge)
    await db_session.flush()

    rows = (await db_session.execute(select(SavedCandidate).where(SavedCandidate.employer_id == owner.id))).scalars().all()
    assert [r.talent_pool_profile_id for r in rows] == [keeper.id]
    assert merge.moved["saved_candidates (already on the kept profile, dropped)"] == 1
    assert merge.moved["interview_list_entries (already on the kept profile, dropped)"] == 1


@pytest.mark.asyncio
async def test_two_copies_with_an_interview_for_the_same_job_are_left_for_a_person(db_session):
    _, job, keeper, loser = await make_pair(db_session)
    await make_interview(db_session, job.id, keeper.id)
    await make_interview(db_session, job.id, loser.id)

    assert await script.interview_conflict(db_session, keeper.id, loser.id) is True


@pytest.mark.asyncio
async def test_an_interview_on_the_copy_alone_moves_over(db_session):
    _, job, keeper, loser = await make_pair(db_session)
    interview = await make_interview(db_session, job.id, loser.id)
    assert await script.interview_conflict(db_session, keeper.id, loser.id) is False
    merge = script.Merge(as_row(keeper), [as_row(loser)], "test")

    await script.merge_one(db_session, merge)
    await db_session.refresh(interview)

    assert interview.talent_pool_profile_id == keeper.id and merge.moved["interviews"] == 1


@pytest.mark.asyncio
async def test_the_empty_text_hash_is_the_one_older_code_gave_every_unreadable_file(db_session):
    assert script.empty_text_hash() == script.hmac.new(
        script.settings.hmac_secret.encode(), b"", script.hashlib.sha256
    ).hexdigest()
    submission = ParsedCVSubmission(filename="x.pdf", parse_status="COMPLETED", cv_text_hash=script.empty_text_hash())
    db_session.add(submission)
    await db_session.flush()
    assert submission.cv_text_hash == script.empty_text_hash()


def test_apply_without_yes_is_refused(capsys):
    assert script.main(["--apply"]) == 2
    assert "Add --yes" in capsys.readouterr().out
