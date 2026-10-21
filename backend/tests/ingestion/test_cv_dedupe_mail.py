"""A CV that arrives by mail follows the same rule as one uploaded by hand.

The two used to disagree: the mail import matched "the newest stored and parsed submission with
this content" and ignored the job, the manual upload matched (content, job), and neither looked at
whose pool it was. So a CV downloaded from the mailbox, uploaded by hand, and then imported was in
the pool twice. These tests run both paths against each other, with the real hash."""

import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select

from app.core.storage import MockStorageService
from app.modules.ai import cv_parsing_service as parsing_module
from app.modules.ai import tasks as ai_tasks
from app.modules.ai.cv_parsing_service import CVParsingService
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import ParsedCVSubmission
from app.modules.ingestion import tasks as ingestion_tasks
from app.modules.ingestion.repository import IngestionRepository
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.talent_pool.schema import TalentPoolSubmitRequest
from app.modules.talent_pool.service import TalentPoolService
from app.modules.users.repository import UserRepository
from tests.conftest import make_employer, make_job

PENDING = CVParsingStatus.PENDING.value
COMPLETED = CVParsingStatus.COMPLETED.value
FAILED = CVParsingStatus.FAILED.value

PDF_ONE = b"%PDF-1.4 the bytes of one file"
PDF_TWO = b"%PDF-1.4 other bytes, the same CV text"
TEXT = "Chidi Okafor, Sales Manager, eight years at Unilever"


@pytest.fixture
def mail(monkeypatch):
    """Everything outside the database stubbed: the text of a PDF is whatever the test says, the
    stored file goes to a mock store, and no Celery task runs."""
    state = SimpleNamespace(
        text=TEXT,
        owner=None,
        provider="gmail",
        pipeline=MagicMock(),
        embedding=MagicMock(),
        storage=MockStorageService(),
    )

    monkeypatch.setattr(
        "app.core.cv_pipeline.layer1_extraction.extract_text_from_pdf",
        lambda data: SimpleNamespace(text=state.text),
    )
    monkeypatch.setattr(parsing_module, "extract_text_from_pdf", lambda data: SimpleNamespace(text=state.text))
    monkeypatch.setattr(parsing_module, "validate_pdf_upload", lambda file, filename: None)
    monkeypatch.setattr("app.core.storage.get_storage_service", lambda: state.storage)
    monkeypatch.setattr(ai_tasks.run_full_pipeline_task, "delay", state.pipeline)
    monkeypatch.setattr(ai_tasks.generate_talent_pool_embedding_task, "delay", state.embedding)
    monkeypatch.setattr(UserRepository, "get_user_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(
        IngestionRepository,
        "get_integration_by_id",
        AsyncMock(side_effect=lambda _id: SimpleNamespace(user_id=state.owner.id, provider=state.provider)
                  if state.owner else None),
    )
    return state


async def employer(db_session):
    user = make_employer()
    db_session.add(user)
    await db_session.flush()
    return user


async def import_cv(db_session, data=PDF_ONE, job=None, filename="cv.pdf"):
    return await ingestion_tasks._process_attachment(
        attachment_data=data,
        filename=filename,
        sender_email="candidate@example.com",
        message_id="msg-1",
        integration_id="integration-1",
        sourced_for_job_id=job.id if job else None,
        db=db_session,
    )


class HandUpload(TalentPoolService):
    """A manual upload with the REAL hash and no parsing: what a person does in the browser."""

    def __init__(self, db_session):
        stub = SimpleNamespace()
        stub.fingerprint = lambda file, filename: CVParsingService.fingerprint(stub, file, filename)
        self.staged = []

        async def stage_cv(uploaded_by, file, filename, cv_text_hash):
            submission = ParsedCVSubmission(
                filename=filename, uploaded_by=uploaded_by.id,
                cv_text_hash=cv_text_hash, parse_status=PENDING,
            )
            db_session.add(submission)
            await db_session.flush()
            self.staged.append(submission)
            return SimpleNamespace(submission=submission, dispatch=lambda: None)

        stub.stage_cv = stage_cv
        super().__init__(db_session, cv_service=stub)

    async def upload(self, user, data=PDF_ONE, job=None):
        request = TalentPoolSubmitRequest(source="referral", sourced_for_job_id=job.id if job else None)
        return await self._add_cv(data, "cv.pdf", request, user, False)


async def profiles_of(db_session, user) -> list[TalentPoolProfiles]:
    result = await db_session.execute(
        select(TalentPoolProfiles).where(TalentPoolProfiles.added_by == user.id)
    )
    return list(result.scalars().all())


async def submissions_of(db_session, user) -> int:
    return (
        await db_session.execute(
            select(func.count()).select_from(ParsedCVSubmission).where(ParsedCVSubmission.uploaded_by == user.id)
        )
    ).scalar_one()


# --- the two paths against each other ---------------------------------------------------


@pytest.mark.asyncio
async def test_a_cv_uploaded_by_hand_then_imported_from_mail_is_in_the_pool_once(db_session, mail):
    """The reported case. The upload by hand is still pending and has no stored file, which made it
    invisible to the mail import, so the import made its own copy."""
    user = mail.owner = await employer(db_session)
    uploaded = await HandUpload(db_session).upload(user)

    outcome = await import_cv(db_session, PDF_TWO)  # a different file, the same CV text

    assert uploaded.status == "queued"
    assert outcome == "deduplicated"
    assert len(await profiles_of(db_session, user)) == 1
    assert await submissions_of(db_session, user) == 1
    mail.pipeline.assert_not_called()  # not parsed a second time


@pytest.mark.asyncio
async def test_a_cv_imported_from_mail_then_uploaded_by_hand_is_in_the_pool_once(db_session, mail):
    user = mail.owner = await employer(db_session)
    assert await import_cv(db_session, PDF_ONE) == "queued"

    uploaded = await HandUpload(db_session).upload(user, PDF_TWO)

    assert uploaded.status == "duplicate"
    assert len(await profiles_of(db_session, user)) == 1
    assert await submissions_of(db_session, user) == 1


@pytest.mark.asyncio
async def test_importing_the_same_mail_twice_adds_it_once(db_session, mail):
    user = mail.owner = await employer(db_session)

    assert await import_cv(db_session) == "queued"
    assert await import_cv(db_session) == "deduplicated"

    assert len(await profiles_of(db_session, user)) == 1
    assert mail.pipeline.call_count == 1


# --- whose pool it is -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_cv_in_another_employers_private_pool_is_not_linked_to_the_importer(db_session, mail):
    first, second = await employer(db_session), await employer(db_session)
    await HandUpload(db_session).upload(first)
    mail.owner = second

    outcome = await import_cv(db_session)

    assert outcome == "queued"
    mine = await profiles_of(db_session, second)
    assert len(mine) == 1 and mine[0].added_by == second.id
    assert len(await profiles_of(db_session, first)) == 1  # theirs is untouched


# --- reusing a parse that is already paid for ---------------------------------------------


@pytest.mark.asyncio
async def test_a_cv_already_parsed_for_someone_else_is_reused_not_parsed_again(db_session, mail):
    other = await employer(db_session)
    parsed = ParsedCVSubmission(
        filename="earlier.pdf", uploaded_by=other.id, parse_status=COMPLETED,
        cv_text_hash=hashlib.sha256(b"").hexdigest(), parsed_data={"skills": ["Excel"], "usable": True},
        r2_key="cv-ingestion/other/earlier.pdf",
    )
    db_session.add(parsed)
    await db_session.flush()
    user = mail.owner = await employer(db_session)
    # Give the earlier parse the hash this CV will have.
    stub = SimpleNamespace()
    parsed.cv_text_hash = CVParsingService.fingerprint(stub, PDF_ONE, "cv.pdf")
    await db_session.flush()

    outcome = await import_cv(db_session)

    assert outcome == "queued"
    [profile] = await profiles_of(db_session, user)
    copy = await db_session.get(ParsedCVSubmission, profile.parsed_submission_id)
    # Its own submission (not the other employer's row), carrying the paid-for parse.
    assert copy.id != parsed.id and copy.uploaded_by == user.id
    assert copy.parsed_data == parsed.parsed_data and copy.r2_key == parsed.r2_key
    assert copy.parse_status == COMPLETED
    mail.pipeline.assert_not_called()
    mail.embedding.assert_called_once_with(str(profile.id))  # so it can be matched


# --- jobs ---------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_import_for_a_job_makes_the_profile_for_that_job(db_session, mail):
    user = mail.owner = await employer(db_session)
    job = make_job(user.id)
    db_session.add(job)
    await db_session.flush()

    await import_cv(db_session, job=job)

    [profile] = await profiles_of(db_session, user)
    assert profile.sourced_for_job_id == job.id


@pytest.mark.asyncio
async def test_a_cv_already_in_the_pool_without_a_job_joins_the_job_it_is_imported_for(db_session, mail):
    user = mail.owner = await employer(db_session)
    job = make_job(user.id)
    db_session.add(job)
    await db_session.flush()
    await import_cv(db_session)

    outcome = await import_cv(db_session, job=job)

    assert outcome == "deduplicated"
    [profile] = await profiles_of(db_session, user)
    assert profile.sourced_for_job_id == job.id


@pytest.mark.asyncio
async def test_a_cv_already_for_a_job_is_not_added_again_by_an_import_with_no_job(db_session, mail):
    user = mail.owner = await employer(db_session)
    job = make_job(user.id)
    db_session.add(job)
    await db_session.flush()
    await import_cv(db_session, job=job)

    assert await import_cv(db_session) == "deduplicated"
    assert len(await profiles_of(db_session, user)) == 1


# --- files with no readable text ------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_different_scans_with_no_text_are_two_candidates_not_one(db_session, mail):
    """Every file with no extractable text used to hash to the same value, so unrelated
    candidates were treated as one CV."""
    user = mail.owner = await employer(db_session)
    mail.text = ""

    first = await import_cv(db_session, b"%PDF-1.4 scan of one person")
    second = await import_cv(db_session, b"%PDF-1.4 scan of someone else")
    again = await import_cv(db_session, b"%PDF-1.4 scan of one person")

    assert (first, second, again) == ("queued", "queued", "deduplicated")
    assert len(await profiles_of(db_session, user)) == 2


# --- when storing the file fails --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_file_that_could_not_be_stored_is_marked_failed_and_is_still_found_next_time(
    db_session, mail, monkeypatch
):
    user = mail.owner = await employer(db_session)
    monkeypatch.setattr(mail.storage, "upload_file", AsyncMock(side_effect=OSError("store is down")))

    with pytest.raises(OSError):
        await import_cv(db_session)

    [profile] = await profiles_of(db_session, user)
    submission = await db_session.get(ParsedCVSubmission, profile.parsed_submission_id)
    assert submission.parse_status == FAILED
    assert "store is down" in submission.error_message
    mail.pipeline.assert_not_called()
    # Saved before the upload, so a retry finds it instead of making a second copy.
    assert await import_cv(db_session) == "deduplicated"


# --- the pipeline gets the stored file ---------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_import_stores_the_file_and_queues_the_parse_with_its_key(db_session, mail):
    user = mail.owner = await employer(db_session)

    assert await import_cv(db_session) == "queued"

    [profile] = await profiles_of(db_session, user)
    submission = await db_session.get(ParsedCVSubmission, profile.parsed_submission_id)
    assert submission.r2_key and submission.r2_key.startswith(f"cv-ingestion/{user.id}/")
    mail.pipeline.assert_called_once_with(
        submission_id=str(submission.id), cache_key=f"cv_parse:{submission.cv_text_hash}", r2_key=submission.r2_key
    )


@pytest.mark.asyncio
async def test_with_nobody_to_own_it_only_the_parse_is_kept(db_session, mail):
    mail.owner = None

    assert await import_cv(db_session) == "queued"

    count = (
        await db_session.execute(
            select(func.count())
            .select_from(ParsedCVSubmission)
            .where(ParsedCVSubmission.uploaded_by.is_(None), ParsedCVSubmission.filename == "cv.pdf")
        )
    ).scalar_one()
    assert count >= 1
