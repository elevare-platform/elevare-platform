"""The same CV is in the talent pool once, whichever way it arrives, and never at the cost
of showing a stranger's profile.

The rule (see talent_pool/dedupe.py): only profiles the uploader can already see count; the same CV
for the same job, or one with no job, is a duplicate; a CV already in the pool WITHOUT a job and
uploaded again for one is attached to that job; the same CV for another job gets its own profile
(a profile holds one score); an archived profile never counts; and it does not matter whether the
earlier copy has finished parsing."""

import asyncio
import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionLocal
from app.modules.ai import cv_parsing_service as parsing_module
from app.modules.ai.cv_parsing_service import CVParsingService, compute_cv_hash
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.talent_pool import service as pool_service
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.schema import TalentPoolSubmitRequest
from app.modules.talent_pool.service import TalentPoolService
from app.modules.users.models import User
from tests.conftest import make_admin, make_employer, make_job
from tests.interviews.conftest import make_talent_pool_profile

PENDING = CVParsingStatus.PENDING.value
COMPLETED = CVParsingStatus.COMPLETED.value


class StubCVService(CVParsingService):
    """The real fingerprint (so the hash rule is the real one), but no parsing and no Celery:
    a staged submission is a plain row and `dispatch` just records that it was called."""

    def __init__(self, db):
        self._db = db
        self.dispatched = []
        self.fail_on = set()

    def fingerprint(self, file: bytes, filename: str) -> str:
        if filename in self.fail_on:
            raise ValueError(f"{filename} is not a valid PDF")
        return hashlib.sha256(file).hexdigest()

    async def stage_cv(self, uploaded_by, file, filename, cv_text_hash):
        submission = ParsedCVSubmission(
            filename=filename,
            uploaded_by=uploaded_by.id,
            cv_text_hash=cv_text_hash,
            parse_status=PENDING,
        )
        self._db.add(submission)
        await self._db.flush()
        return SimpleNamespace(
            submission=submission, dispatch=lambda: self.dispatched.append(submission.id)
        )


@pytest.fixture
def scoring(monkeypatch):
    queued = MagicMock()
    monkeypatch.setattr(pool_service.score_talent_pool_profile_task, "delay", queued)
    return queued


def payload(job_id=None) -> TalentPoolSubmitRequest:
    return TalentPoolSubmitRequest(source="referral", sourced_for_job_id=job_id)


async def employer(db_session):
    user = make_employer()
    db_session.add(user)
    await db_session.flush()
    return user


async def job_for(db_session, owner):
    job = make_job(owner.id)
    db_session.add(job)
    await db_session.flush()
    return job


def pool(db_session):
    stub = StubCVService(db_session)
    return TalentPoolService(db_session, cv_service=stub), stub


async def add(service, user, cv: bytes, job=None, name="cv.pdf", auto_score=True):
    return await service._add_cv(cv, name, payload(job.id if job else None), user, auto_score)


async def profiles_of(db_session, user) -> int:
    """How many profiles this user has (the database holds other people's rows too)."""
    return (
        await db_session.execute(
            select(func.count())
            .select_from(TalentPoolProfiles)
            .where(TalentPoolProfiles.added_by == user.id)
        )
    ).scalar_one()


async def submissions_of(db_session, user) -> int:
    return (
        await db_session.execute(
            select(func.count())
            .select_from(ParsedCVSubmission)
            .where(ParsedCVSubmission.uploaded_by == user.id)
        )
    ).scalar_one()


async def existing_cv(db_session, owner, cv: bytes, job=None, parse_status=PENDING, **row):
    """A profile already in the pool for this CV, with its submission."""
    submission = ParsedCVSubmission(
        filename="earlier.pdf",
        parse_status=parse_status,
        cv_text_hash=hashlib.sha256(cv).hexdigest(),
        uploaded_by=owner.id,
    )
    db_session.add(submission)
    await db_session.flush()
    return await make_talent_pool_profile(
        db_session,
        owner.id,
        parsed_submission_id=submission.id,
        sourced_for_job_id=job.id if job else None,
        **row,
    )


CV = b"%PDF-1.4 Chidi Okafor, Sales Manager, 8 years"
OTHER_CV = b"%PDF-1.4 Ngozi Eze, Accountant, 3 years"


# --- the same CV twice -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_same_cv_for_the_same_job_is_added_once(db_session, scoring):
    service, stub = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)

    first = await add(service, user, CV, job)
    second = await add(service, user, CV, job, name="again.pdf")

    assert (first.status, second.status) == ("queued", "duplicate")
    assert second.profile.id == first.profile.id
    assert await profiles_of(db_session, user) == 1


@pytest.mark.asyncio
async def test_a_duplicate_leaves_no_submission_without_a_profile(db_session, scoring):
    """A duplicate upload used to create a submission first and then find the duplicate, leaving
    a submission with no profile behind it."""
    service, stub = pool(db_session)
    user = await employer(db_session)

    await add(service, user, CV)
    await add(service, user, CV)
    await add(service, user, CV)

    assert await submissions_of(db_session, user) == 1
    assert len(stub.dispatched) == 1  # parsed once, however many times it was uploaded


@pytest.mark.asyncio
async def test_the_same_cv_with_no_job_twice_is_one_profile(db_session, scoring):
    service, _ = pool(db_session)
    user = await employer(db_session)

    first = await add(service, user, CV)
    second = await add(service, user, CV)

    assert second.status == "duplicate" and second.profile.id == first.profile.id


@pytest.mark.asyncio
async def test_a_different_cv_is_not_mistaken_for_it(db_session, scoring):
    service, _ = pool(db_session)
    user = await employer(db_session)

    await add(service, user, CV)
    other = await add(service, user, OTHER_CV)

    assert other.status == "queued"
    assert await profiles_of(db_session, user) == 2


# --- jobs --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_cv_already_in_the_pool_with_no_job_joins_the_job_it_is_uploaded_for(
    db_session, scoring
):
    service, _ = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)
    first = await add(service, user, CV)  # uploaded with no job

    second = await add(service, user, CV, job)  # uploaded again for a job

    assert second.status == "attached"
    assert second.profile.id == first.profile.id
    assert second.profile.sourced_for_job_id == job.id
    assert await profiles_of(db_session, user) == 1
    scoring.assert_called_once_with(str(first.profile.id))  # now scored against that job


@pytest.mark.asyncio
async def test_attaching_does_not_score_when_the_plan_does_not_allow_it(db_session, scoring):
    service, _ = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)
    await add(service, user, CV)

    await add(service, user, CV, job, auto_score=False)

    scoring.assert_not_called()


@pytest.mark.asyncio
async def test_a_cv_already_for_a_job_uploaded_again_with_no_job_is_a_duplicate(db_session, scoring):
    service, _ = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)
    first = await add(service, user, CV, job)

    second = await add(service, user, CV)

    assert second.status == "duplicate"
    assert second.profile.id == first.profile.id
    assert second.profile.sourced_for_job_id == job.id  # says which job it is already linked to


@pytest.mark.asyncio
async def test_the_same_cv_for_another_job_gets_its_own_profile(db_session, scoring):
    """A profile holds ONE score, so sharing it between two jobs would stop it being ranked
    in the second one."""
    service, _ = pool(db_session)
    user = await employer(db_session)
    job_a, job_b = await job_for(db_session, user), await job_for(db_session, user)

    first = await add(service, user, CV, job_a)
    second = await add(service, user, CV, job_b)

    assert second.status == "queued"
    assert second.profile.id != first.profile.id
    assert {first.profile.sourced_for_job_id, second.profile.sourced_for_job_id} == {job_a.id, job_b.id}


@pytest.mark.asyncio
async def test_a_new_profile_is_scored_only_when_it_has_a_job_and_the_plan_allows_it(
    db_session, scoring
):
    service, _ = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)

    await add(service, user, CV)  # no job: nothing to score against
    scoring.assert_not_called()
    created = await add(service, user, OTHER_CV, job)

    scoring.assert_called_once_with(str(created.profile.id))


# --- whose pool it is --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_another_employers_private_profile_is_never_returned_or_linked(db_session, scoring):
    service, _ = pool(db_session)
    first_employer, second_employer = await employer(db_session), await employer(db_session)
    theirs = await add(service, first_employer, CV)

    mine = await add(service, second_employer, CV)

    assert mine.status == "queued"
    assert mine.profile.id != theirs.profile.id
    assert mine.profile.added_by == second_employer.id
    assert theirs.profile.added_by == first_employer.id
    assert theirs.profile.sourced_for_job_id is None  # untouched


@pytest.mark.asyncio
async def test_a_cv_the_platform_already_holds_is_a_duplicate_for_every_employer(db_session, scoring):
    service, _ = pool(db_session)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    platform = await existing_cv(db_session, admin, CV)
    user = await employer(db_session)

    result = await add(service, user, CV)

    assert result.status == "duplicate"
    assert result.profile.id == platform.id


@pytest.mark.asyncio
async def test_an_employer_does_not_attach_their_job_to_a_profile_the_platform_owns(
    db_session, scoring
):
    service, _ = pool(db_session)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()
    platform = await existing_cv(db_session, admin, CV)
    user = await employer(db_session)
    job = await job_for(db_session, user)

    result = await add(service, user, CV, job)

    assert result.status == "queued"
    assert result.profile.id != platform.id
    assert platform.sourced_for_job_id is None


@pytest.mark.asyncio
async def test_an_admin_upload_never_attaches_to_an_employers_private_profile(db_session, scoring):
    service, _ = pool(db_session)
    owner = await employer(db_session)
    private = await existing_cv(db_session, owner, CV)
    admin = make_admin()
    db_session.add(admin)
    await db_session.flush()

    result = await add(service, admin, CV)

    assert result.status == "queued"
    assert result.profile.id != private.id
    assert result.profile.added_by == admin.id


# --- what does not matter ----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("parse_status", [PENDING, COMPLETED, CVParsingStatus.FAILED.value])
async def test_it_does_not_matter_whether_the_earlier_copy_has_finished_parsing(
    db_session, scoring, parse_status
):
    """A copy that is still pending, or has no stored file yet, used to be invisible to the
    mail import, so it made its own copy."""
    service, _ = pool(db_session)
    user = await employer(db_session)
    earlier = await existing_cv(db_session, user, CV, parse_status=parse_status)

    result = await add(service, user, CV)

    assert result.status == "duplicate" and result.profile.id == earlier.id


@pytest.mark.asyncio
async def test_an_archived_profile_does_not_count_so_the_cv_can_be_added_again(db_session, scoring):
    service, _ = pool(db_session)
    user = await employer(db_session)
    await existing_cv(db_session, user, CV, status="archived")

    result = await add(service, user, CV)

    assert result.status == "queued"


# --- the answer a person gets ------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_single_upload_that_was_already_there_says_so(db_session, scoring):
    service, _ = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)
    await add(service, user, CV, job)
    service._can_auto_score = AsyncMock(return_value=True)

    again = await service.submit(CV, "again.pdf", payload(job.id), user)
    new = await service.submit(OTHER_CV, "new.pdf", payload(job.id), user)

    assert again.already_in_pool is True and again.sourced_for_job_id == job.id
    assert new.already_in_pool is False


@pytest.mark.asyncio
async def test_a_batch_reports_each_file_and_one_bad_file_does_not_stop_the_rest(db_session, scoring):
    service, stub = pool(db_session)
    user = await employer(db_session)
    job = await job_for(db_session, user)
    await add(service, user, OTHER_CV)  # already there, with no job
    stub.fail_on = {"broken.pdf"}
    service._can_auto_score = AsyncMock(return_value=True)

    results = await service.submit_batch(
        [(CV, "a.pdf"), (CV, "a-copy.pdf"), (b"junk", "broken.pdf"), (OTHER_CV, "b.pdf")],
        payload(job.id),
        user,
    )

    assert [r["status"] for r in results] == ["queued", "duplicate", "failed", "attached"]
    assert results[0]["profile_id"] == results[1]["profile_id"]
    assert results[1]["submission_id"] is None  # nothing was created for the duplicate
    assert results[0]["linked_job_id"] == str(job.id)
    assert "not a valid PDF" in results[2]["error"]


# --- two at the same moment --------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_uploads_of_the_same_cv_at_the_same_moment_make_one_profile(scoring):
    """Real, separate database sessions and real commits: the second waits for the first and then
    finds its profile. (Everything it creates is deleted again.)"""
    email = f"dedupe_{uuid.uuid4().hex[:8]}@example.com"
    cv = f"%PDF-1.4 concurrent {uuid.uuid4().hex}".encode()
    created_user_id = None
    try:
        async with AsyncSessionLocal() as setup:
            user = make_employer(email=email)
            setup.add(user)
            await setup.commit()
            created_user_id = user.id

        async def upload(filename):
            async with AsyncSessionLocal() as session:
                service = TalentPoolService(session, cv_service=StubCVService(session))
                owner = await session.get(User, created_user_id)
                return await service._add_cv(cv, filename, payload(), owner, False)

        results = await asyncio.gather(upload("one.pdf"), upload("two.pdf"), upload("three.pdf"))

        assert sorted(r.status for r in results) == ["duplicate", "duplicate", "queued"]
        assert len({r.profile.id for r in results}) == 1
        async with AsyncSessionLocal() as check:
            profiles = (
                await check.execute(
                    select(func.count())
                    .select_from(TalentPoolProfiles)
                    .where(TalentPoolProfiles.added_by == created_user_id)
                )
            ).scalar_one()
        assert profiles == 1
    finally:
        if created_user_id:
            async with AsyncSessionLocal() as cleanup:
                await cleanup.execute(
                    delete(TalentPoolProfiles).where(TalentPoolProfiles.added_by == created_user_id)
                )
                await cleanup.execute(
                    delete(ParsedCVSubmission).where(ParsedCVSubmission.uploaded_by == created_user_id)
                )
                await cleanup.execute(delete(User).where(User.id == created_user_id))
                await cleanup.commit()


# --- the hash -----------------------------------------------------------------------------


def test_a_cv_is_identified_by_its_text_not_its_bytes():
    assert compute_cv_hash("Chidi Okafor", b"file one") == compute_cv_hash("Chidi Okafor", b"file two")
    assert compute_cv_hash("Chidi Okafor", b"x") != compute_cv_hash("Ngozi Eze", b"x")


@pytest.mark.parametrize("empty", ["", "   \n\t ", None])
def test_two_different_files_with_no_readable_text_are_not_the_same_cv(empty):
    """Hashing the empty text gave every such file the SAME hash, so unrelated candidates were
    treated as one CV."""
    assert compute_cv_hash(empty, b"scan of person one") != compute_cv_hash(empty, b"scan of person two")
    assert compute_cv_hash(empty, b"same scan") == compute_cv_hash(empty, b"same scan")


def test_the_manual_upload_uses_that_same_hash(monkeypatch):
    monkeypatch.setattr(parsing_module, "validate_pdf_upload", lambda file, filename: None)
    monkeypatch.setattr(
        parsing_module, "extract_text_from_pdf", lambda file: SimpleNamespace(text="Chidi Okafor")
    )
    service = CVParsingService.__new__(CVParsingService)

    assert service.fingerprint(b"any bytes", "cv.pdf") == compute_cv_hash("Chidi Okafor", b"other bytes")


def test_an_invalid_upload_is_refused_before_anything_is_created(monkeypatch):
    def refuse(file, filename):
        raise ValueError("not a PDF")

    monkeypatch.setattr(parsing_module, "validate_pdf_upload", refuse)
    service = CVParsingService.__new__(CVParsingService)

    with pytest.raises(ValueError):
        service.fingerprint(b"junk", "cv.pdf")
