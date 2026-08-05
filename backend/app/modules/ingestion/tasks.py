"""Celery tasks for the candidate ingestion pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import re
import time
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.celery_app import celery
from app.core.config import settings
from app.modules.ingestion.enums import (
    STALE_RUN_TIMEOUT,
    ImportStatus,
    IntegrationStatus,
    MailProvider,
)
from app.modules.talent_pool.enums import SourceType

logger = logging.getLogger(__name__)

_RATE_LIMIT_DELAY = 0.15
_MAX_PAGES = 200
# Deliberately kept low. Each concurrent fetch holds a full attachment's
# bytes in memory (resp.content — not streamed) until _process_attachment
# finishes with them. On a page with several multi-MB PDFs, too-high
# concurrency inside a single forked worker process spikes memory past the
# container limit, causing the OOM killer to send SIGKILL (WorkerLostError /
# signal 9). 3 is still meaningfully faster than sequential while keeping
# peak memory predictable.
_FETCH_CONCURRENCY = 3
# A run checkpoints and hands off to a fresh task execution once it's been
# going this long, rather than risking the task's own 2-hour hard time_limit
# SIGKILL-ing it mid-page — a hard kill bypasses all cleanup, which is what
# left runs stuck in RUNNING before the stale-run recovery fix. Comfortably
# under the hard limit to leave room for whatever page is in flight.
_TASK_DEADLINE_SECONDS = 90 * 60


def _compute_cv_hash(content: bytes | str) -> str:
    data = content.encode() if isinstance(content, str) else content
    return hmac.new(
        settings.hmac_secret.encode(),
        data,
        hashlib.sha256,
    ).hexdigest()


def _sanitize_filename(filename: str) -> str:
    """Strip path components and control characters from a sender-supplied
    attachment filename before it's stored — email attachment filenames
    are fully attacker-controlled (e.g. "../../etc/passwd" or embedded
    newlines) and are displayed as-is in the Talent Pool UI."""
    name = os.path.basename((filename or "").strip()) or "attachment"
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return name[:255] or "attachment"


def _source_for_provider(provider: str) -> tuple[str, str]:
    """Map a MailIntegration.provider to its SourceType and a human label
    for the source_note prefix — so Zoho-sourced candidates are recorded
    (and later filterable/displayed) as Zoho imports, not Gmail imports."""
    if provider == MailProvider.ZOHO.value:
        return SourceType.ZOHO_IMPORT.value, "Zoho import"
    return SourceType.GMAIL_IMPORT.value, "Gmail import"


async def _list_messages_with_refresh(
    service, integration_id, adapter, query, max_results, page_token
):
    """adapter.list_messages, retrying once after a token refresh on a 401."""
    try:
        return await adapter.list_messages(
            query=query, max_results=max_results, page_token=page_token
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 401:
            raise
        await service.ensure_fresh_token(integration_id, adapter)
        return await adapter.list_messages(
            query=query, max_results=max_results, page_token=page_token
        )


async def _get_message_with_refresh(service, integration_id, adapter, message_id):
    """adapter.get_message, retrying once after a token refresh on a 401.

    Historical imports can run for up to two hours; OAuth access tokens
    typically last about an hour. The proactive per-page refresh in the
    caller covers the common case — this is the backstop for whatever it
    doesn't catch in time (e.g. a token that lapses mid-page).
    """
    try:
        return await adapter.get_message(message_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 401:
            raise
        await service.ensure_fresh_token(integration_id, adapter)
        return await adapter.get_message(message_id)


async def _fetch_and_process_messages(
    service, integration_id, adapter, message_ids, handle_message
):
    """Fetch a page's messages with bounded concurrency, handing each one to
    `handle_message` as soon as its own fetch completes — instead of
    fetching the entire page first and processing afterward.

    With up to 500 message IDs per page, gathering every fetched message
    (attachment bytes included) before any of them were filtered or
    discarded meant the whole page was alive in memory at once, regardless
    of how low fetch concurrency was set — that's what kept OOM-killing the
    worker even after fetch concurrency was capped. Processing each message
    right after its own fetch bounds memory to roughly _FETCH_CONCURRENCY
    messages at a time instead of the whole page.

    Fetching runs concurrently (bounded by _FETCH_CONCURRENCY); processing
    runs serialized under a lock, since AsyncSession isn't safe for
    concurrent use from multiple coroutines.

    Returns a list of (message_id, outcome, exception_or_None) in the same
    order as message_ids, where outcome is "handled", "fetch_failed", or
    "process_failed" (handle_message itself raised).
    """
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)
    process_lock = asyncio.Lock()

    async def _fetch_and_handle_one(message_id):
        async with semaphore:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            try:
                message = await _get_message_with_refresh(
                    service, integration_id, adapter, message_id
                )
            except Exception as exc:
                return message_id, "fetch_failed", exc

        async with process_lock:
            try:
                await handle_message(message_id, message)
                return message_id, "handled", None
            except Exception as exc:
                return message_id, "process_failed", exc

    return await asyncio.gather(
        *[_fetch_and_handle_one(mid) for mid in message_ids]
    )


@celery.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    time_limit=60 * 120,
    soft_time_limit=60 * 110,
)
def run_historical_import_task(self, run_id, integration_id, sourced_for_job_id=None):
    asyncio.run(_run_import_async(run_id, integration_id, sourced_for_job_id))


async def _run_import_async(
    run_id_str, integration_id_str, sourced_for_job_id_str=None
):
    from app.core.storage import get_storage_service
    from app.modules.ingestion.attachment_filter import filter_message
    from app.modules.ingestion.repository import IngestionRepository
    from app.modules.ingestion.service import IngestionService

    run_id = uuid.UUID(run_id_str)
    integration_id = uuid.UUID(integration_id_str)
    sourced_for_job_id = (
        uuid.UUID(sourced_for_job_id_str) if sourced_for_job_id_str else None
    )

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with SessionLocal() as db:
        repo = IngestionRepository(db)
        service = IngestionService(db, get_storage_service())

        run = await repo.get_import_run(run_id)
        if not run:
            logger.error("Import run %s not found", run_id)
            return

        integration = await repo.get_integration_by_id(integration_id)
        if not integration:
            await repo.update_import_run(
                run_id,
                {
                    "status": ImportStatus.FAILED.value,
                    "error_message": "Integration not found",
                    "completed_at": datetime.now(UTC),
                },
            )
            await db.commit()
            return

        await repo.update_import_run(
            run_id,
            {
                "status": ImportStatus.RUNNING.value,
                # Only set on the true first start — a resumed run's
                # started_at should reflect when the whole import began,
                # not when this particular checkpointed execution picked
                # it back up.
                **({"started_at": datetime.now(UTC)} if run.started_at is None else {}),
            },
        )
        await db.commit()

        # Resume from where a previous execution of this same run left off,
        # if it checkpointed — both the counts and the pagination cursor —
        # instead of restarting the whole mailbox from page one.
        total_found = run.total_emails_found or 0
        processed = run.emails_processed or 0
        skipped = run.emails_skipped or 0
        failed = run.emails_failed or 0
        deduplicated = run.emails_deduplicated or 0

        task_start_monotonic = time.monotonic()

        try:
            adapter = await service.get_valid_adapter(integration)
            query = run.query_filter or "has:attachment"
            page_token = run.resume_page_token
            pages_fetched = 0

            while pages_fetched < _MAX_PAGES:
                await service.ensure_fresh_token(integration_id, adapter)
                message_ids, page_token = await _list_messages_with_refresh(
                    service, integration_id, adapter, query, 500, page_token
                )
                if not message_ids:
                    break

                total_found += len(message_ids)
                pages_fetched += 1

                async def handle_message(message_id, message):
                    nonlocal processed, skipped, deduplicated, failed
                    result = filter_message(message)
                    if not result.passed:
                        skipped += 1
                        return
                    for attachment in result.cv_attachments:
                        try:
                            outcome = await _process_attachment(
                                attachment_data=attachment.data,
                                filename=attachment.filename,
                                sender_email=message.sender_email,
                                message_id=message_id,
                                integration_id=integration_id,
                                sourced_for_job_id=sourced_for_job_id,
                                db=db,
                            )
                            if outcome == "deduplicated":
                                deduplicated += 1
                            else:
                                processed += 1
                        except Exception:
                            logger.warning(
                                "Failed to process attachment %s",
                                attachment.filename,
                                exc_info=True,
                            )
                            failed += 1

                # Fetch and process this page's messages together, one at a
                # time as each fetch completes, rather than fetching the
                # whole page (up to 500 messages) into memory before any of
                # it is processed or discarded — see _fetch_and_process_messages.
                fetch_results = await _fetch_and_process_messages(
                    service, integration_id, adapter, message_ids, handle_message
                )

                for message_id, outcome, exc in fetch_results:
                    if outcome == "fetch_failed":
                        logger.warning(
                            "Failed to fetch message %s", message_id, exc_info=exc
                        )
                        failed += 1
                    elif outcome == "process_failed":
                        logger.warning(
                            "Unhandled error handling message %s",
                            message_id,
                            exc_info=exc,
                        )
                        failed += 1

                # Persist progress after every page, not just at the very end —
                # otherwise a large mailbox leaves the UI showing 0 processed/
                # skipped/failed for the entire run (it only reads what's in
                # the DB), even though real work is happening. total_emails_found
                # is written in this same update, together with the counts for
                # the page it belongs to — writing it earlier (right after the
                # page was fetched, before it was processed) made the progress
                # bar's denominator jump ahead of its numerator for the entire
                # time that page took to process, which reads as progress going
                # backwards rather than forwards.
                await repo.update_import_run(
                    run_id,
                    {
                        "total_emails_found": total_found,
                        "emails_processed": processed,
                        "emails_skipped": skipped,
                        "emails_failed": failed,
                        "emails_deduplicated": deduplicated,
                    },
                )
                await db.commit()

                if not page_token:
                    break

                # Checkpoint and hand off to a fresh task execution rather
                # than risk running past the hard time_limit — that would
                # get SIGKILLed, which skips all cleanup below (including
                # the except block) and is exactly what left runs stuck in
                # RUNNING before the stale-run recovery fix. The handoff
                # task resumes from resume_page_token with today's counts
                # already persisted above, so nothing is lost or redone.
                if time.monotonic() - task_start_monotonic > _TASK_DEADLINE_SECONDS:
                    await repo.update_import_run(
                        run_id, {"resume_page_token": page_token}
                    )
                    await db.commit()
                    run_historical_import_task.delay(
                        run_id_str, integration_id_str, sourced_for_job_id_str
                    )
                    logger.info(
                        "Import run %s checkpointed after %d page(s) — "
                        "handed off to a new task execution",
                        run_id,
                        pages_fetched,
                    )
                    return

            try:
                new_cursor = await adapter.get_current_history_id()
                await repo.update_integration(
                    integration_id,
                    {"sync_cursor": new_cursor, "last_synced_at": datetime.now(UTC)},
                )
            except Exception:
                logger.warning("Failed to update sync cursor", exc_info=True)

            await repo.update_import_run(
                run_id,
                {
                    "status": ImportStatus.COMPLETED.value,
                    "total_emails_found": total_found,
                    "emails_processed": processed,
                    "emails_skipped": skipped,
                    "emails_failed": failed,
                    "emails_deduplicated": deduplicated,
                    "resume_page_token": None,
                    "completed_at": datetime.now(UTC),
                },
            )
            await db.commit()
            logger.info(
                "Import run %s completed — found=%d processed=%d skipped=%d failed=%d dedup=%d",
                run_id,
                total_found,
                processed,
                skipped,
                failed,
                deduplicated,
            )

        except Exception as exc:
            logger.exception("Import run %s failed", run_id)
            await repo.update_import_run(
                run_id,
                {
                    "status": ImportStatus.FAILED.value,
                    "emails_processed": processed,
                    "emails_skipped": skipped,
                    "emails_failed": failed,
                    "emails_deduplicated": deduplicated,
                    "error_message": str(exc),
                    "completed_at": datetime.now(UTC),
                },
            )
            await repo.update_integration(
                integration_id,
                {"status": IntegrationStatus.ERROR.value, "error_message": str(exc)},
            )
            await db.commit()
            raise
        finally:
            await engine.dispose()


@celery.task(time_limit=60 * 5, soft_time_limit=60 * 4)
def reap_stale_import_runs_task():
    """Celery Beat task — periodically marks orphaned import runs as failed.

    A run stays RUNNING/PENDING forever if the worker process running it
    dies mid-task (OOM kill, the task's own hard time_limit, a container
    restart) — those bypass the task's except-block cleanup entirely, so
    nothing else ever moves the row out of RUNNING. Left alone, that
    permanently blocks new imports and incremental sync for the affected
    integration. See STALE_RUN_TIMEOUT for the staleness threshold.
    """
    asyncio.run(_reap_stale_runs_async())


async def _reap_stale_runs_async():
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            from app.modules.ingestion.repository import IngestionRepository

            repo = IngestionRepository(db)
            cutoff = datetime.now(UTC) - STALE_RUN_TIMEOUT
            stale_runs = await repo.get_stale_running_runs(cutoff)
            if not stale_runs:
                return

            for run in stale_runs:
                await repo.update_import_run(
                    run.id,
                    {
                        "status": ImportStatus.FAILED.value,
                        "error_message": "Import timed out — the worker likely "
                        "crashed mid-run. Marked failed automatically.",
                        "completed_at": datetime.now(UTC),
                    },
                )
            await db.commit()
            logger.warning(
                "reap_stale_import_runs: marked %d orphaned run(s) failed",
                len(stale_runs),
            )
    finally:
        await engine.dispose()


@celery.task(time_limit=60 * 12, soft_time_limit=60 * 11)
def sync_all_mailboxes_task():
    """Celery Beat task — every 15 minutes, syncs all CONNECTED mailboxes with a cursor."""
    asyncio.run(_sync_all_async())


async def _sync_all_async():
    from sqlalchemy import select

    from app.modules.ingestion.models import MailIntegration

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(MailIntegration).where(
                    MailIntegration.status == IntegrationStatus.CONNECTED.value,
                    MailIntegration.sync_cursor.is_not(None),
                )
            )
            integrations = list(result.scalars().all())

        if not integrations:
            return

        logger.info("sync_all: syncing %d integration(s)", len(integrations))
        for integration in integrations:
            try:
                await _sync_one(integration)
            except Exception:
                logger.exception("sync_all: failed for %s", integration.id)
    finally:
        await engine.dispose()


async def _sync_one(integration):
    from app.core.storage import get_storage_service
    from app.modules.ingestion.attachment_filter import filter_message
    from app.modules.ingestion.repository import IngestionRepository
    from app.modules.ingestion.service import IngestionService

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async with SessionLocal() as db:
        repo = IngestionRepository(db)
        service = IngestionService(db, get_storage_service())

        fresh = await repo.get_integration_by_id(integration.id)
        if not fresh or fresh.sync_cursor is None:
            return

        try:
            adapter = await service.get_valid_adapter(fresh)
        except Exception as e:
            await repo.update_integration(
                fresh.id,
                {
                    "status": IntegrationStatus.ERROR.value,
                    "error_message": f"Token refresh failed: {e}",
                },
            )
            await db.commit()
            return

        try:
            new_ids, new_cursor = await adapter.get_history_since(fresh.sync_cursor)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 410):
                await repo.update_integration(
                    fresh.id,
                    {
                        "status": IntegrationStatus.ERROR.value,
                        "error_message": "Sync cursor expired. Run a new historical import.",
                    },
                )
                await db.commit()
            return
        except Exception:
            logger.warning(
                "sync_one: get_history_since failed for %s", fresh.id, exc_info=True
            )
            return

        if not new_ids:
            await repo.update_integration(
                fresh.id,
                {"sync_cursor": new_cursor, "last_synced_at": datetime.now(UTC)},
            )
            await db.commit()
            return

        logger.info(
            "sync_one: %d new message(s) for %s", len(new_ids), fresh.email_address
        )
        processed = skipped = failed = deduplicated = 0

        for message_id in new_ids:
            await asyncio.sleep(_RATE_LIMIT_DELAY)
            try:
                message = await _get_message_with_refresh(
                    service, fresh.id, adapter, message_id
                )
            except Exception:
                failed += 1
                continue

            result = filter_message(message)
            if not result.passed:
                skipped += 1
                continue

            for attachment in result.cv_attachments:
                try:
                    outcome = await _process_attachment(
                        attachment_data=attachment.data,
                        filename=attachment.filename,
                        sender_email=message.sender_email,
                        message_id=message_id,
                        integration_id=fresh.id,
                        sourced_for_job_id=None,
                        db=db,
                    )
                    if outcome == "deduplicated":
                        deduplicated += 1
                    else:
                        processed += 1
                except Exception:
                    failed += 1

        await repo.update_integration(
            fresh.id,
            {
                "sync_cursor": new_cursor,
                "last_synced_at": datetime.now(UTC),
                "status": IntegrationStatus.CONNECTED.value,
                "error_message": None,
            },
        )
        await db.commit()
        logger.info(
            "sync_one: done %s — processed=%d skipped=%d dedup=%d failed=%d",
            fresh.email_address,
            processed,
            skipped,
            deduplicated,
            failed,
        )

    await engine.dispose()


async def _process_attachment(
    attachment_data,
    filename,
    sender_email,
    message_id,
    integration_id,
    sourced_for_job_id,
    db,
):
    from sqlalchemy import select as _select

    from app.core.cv_pipeline.layer1_extraction import extract_text_from_pdf
    from app.core.storage import get_storage_service
    from app.modules.ai.cv_parsing_repo import CVParsingRepo
    from app.modules.ai.enums import CVParsingStatus
    from app.modules.ai.tasks import run_full_pipeline_task
    from app.modules.ingestion.repository import IngestionRepository
    from app.modules.talent_pool.models import TalentPoolProfiles
    from app.modules.users.repository import UserRepository

    filename = _sanitize_filename(filename)

    try:
        text_result = extract_text_from_pdf(attachment_data)
        cv_text = text_result.text or ""
    except Exception:
        cv_text = ""

    cv_hash = (
        _compute_cv_hash(cv_text)
        if cv_text.strip()
        else _compute_cv_hash(attachment_data)
    )
    storage = get_storage_service()
    parsing_repo = CVParsingRepo(db, storage)

    existing = await parsing_repo.get_with_r2_key_by_hash(cv_hash)
    if existing:
        existing_tp = await db.execute(
            _select(TalentPoolProfiles).where(
                TalentPoolProfiles.parsed_submission_id == existing.id
            )
        )
        if not existing_tp.scalar_one_or_none():
            ingestion_repo = IngestionRepository(db)
            integration = await ingestion_repo.get_integration_by_id(integration_id)
            owner_id = integration.user_id if integration else None
            if owner_id:
                source_value, source_label = _source_for_provider(
                    integration.provider if integration else ""
                )
                db.add(
                    TalentPoolProfiles(
                        parsed_submission_id=existing.id,
                        source=source_value,
                        source_note=f"{source_label} — {sender_email} · message {message_id}",
                        sourced_for_job_id=sourced_for_job_id,
                        added_by=owner_id,
                    )
                )
                await db.commit()
        return "deduplicated"

    user_repo = UserRepository(db)
    uploader_user = await user_repo.get_user_by_email(sender_email)
    uploader_id = uploader_user.id if uploader_user else None

    ingestion_repo = IngestionRepository(db)
    integration = await ingestion_repo.get_integration_by_id(integration_id)
    owner_id = integration.user_id if integration else uploader_id
    source_value, source_label = _source_for_provider(
        integration.provider if integration else ""
    )

    submission = await parsing_repo.submit_cv_for_parsing(
        filename=filename,
        uploaded_by_id=owner_id,
        cv_text_hash=cv_hash,
        parse_status=CVParsingStatus.PENDING,
        r2_key=None,
    )
    await db.flush()

    if owner_id:
        db.add(
            TalentPoolProfiles(
                parsed_submission_id=submission.id,
                source=source_value,
                source_note=f"{source_label} — {sender_email} · message {message_id}",
                sourced_for_job_id=sourced_for_job_id,
                added_by=owner_id,
            )
        )

    # Upload to R2 now so the pipeline task receives only the key.
    # This keeps large file bytes out of Redis/Celery messages entirely,
    # preventing OOM kills on the worker during large mailbox imports.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
    mime_map = {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
    }
    content_type = mime_map.get(ext, "application/octet-stream")
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    r2_key = f"cv-ingestion/{owner_id or 'system'}/{timestamp}_{filename}"
    await storage.upload_file(attachment_data, r2_key, content_type)
    await parsing_repo.update(submission.id, {"r2_key": r2_key})

    await db.commit()

    # Pass r2_key instead of file bytes — pipeline downloads from R2 when it runs
    run_full_pipeline_task.delay(
        submission_id=str(submission.id),
        cache_key=f"cv_parse:{cv_hash}",
        r2_key=r2_key,
    )
    logger.debug(
        "Queued pipeline for %s (submission %s, r2=%s)", filename, submission.id, r2_key
    )
    return "queued"
