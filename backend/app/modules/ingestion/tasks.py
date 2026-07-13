"""Celery tasks for the candidate ingestion pipeline."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.celery_app import celery
from app.core.config import settings
from app.modules.ingestion.enums import ImportStatus, IntegrationStatus

logger = logging.getLogger(__name__)

_RATE_LIMIT_DELAY = 0.15
_MAX_PAGES = 200


def _compute_cv_hash(text: str) -> str:
    return hmac.new(
        settings.hmac_secret.encode(),
        text.encode(),
        hashlib.sha256,
    ).hexdigest()


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
            {"status": ImportStatus.RUNNING.value, "started_at": datetime.now(UTC)},
        )
        await db.commit()

        total_found = processed = skipped = failed = deduplicated = 0

        try:
            adapter = await service.get_valid_adapter(integration)
            query = run.query_filter or "has:attachment"
            page_token = None
            pages_fetched = 0

            while pages_fetched < _MAX_PAGES:
                message_ids, page_token = await adapter.list_messages(
                    query=query, max_results=500, page_token=page_token
                )
                if not message_ids:
                    break

                total_found += len(message_ids)
                pages_fetched += 1
                await repo.update_import_run(
                    run_id, {"total_emails_found": total_found}
                )
                await db.commit()

                for message_id in message_ids:
                    await asyncio.sleep(_RATE_LIMIT_DELAY)
                    try:
                        message = await adapter.get_message(message_id)
                    except Exception:
                        logger.warning(
                            "Failed to fetch message %s", message_id, exc_info=True
                        )
                        failed += 1
                        continue

                    from app.modules.ingestion.attachment_filter import filter_message

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

                if not page_token:
                    break

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
    import httpx

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
                message = await adapter.get_message(message_id)
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
    from app.modules.talent_pool.enums import SourceType
    from app.modules.talent_pool.models import TalentPoolProfiles
    from app.modules.users.repository import UserRepository

    try:
        text_result = extract_text_from_pdf(attachment_data)
        cv_text = text_result.text or ""
    except Exception:
        cv_text = ""

    cv_hash = _compute_cv_hash(cv_text)
    parsing_repo = CVParsingRepo(db, get_storage_service())

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
                db.add(
                    TalentPoolProfiles(
                        parsed_submission_id=existing.id,
                        source=SourceType.GMAIL_IMPORT.value,
                        source_note=f"Gmail import — {sender_email} · message {message_id}",
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
                source=SourceType.GMAIL_IMPORT.value,
                source_note=f"Gmail import — {sender_email} · message {message_id}",
                sourced_for_job_id=sourced_for_job_id,
                added_by=owner_id,
            )
        )

    await db.commit()
    run_full_pipeline_task.delay(
        submission_id=str(submission.id),
        cache_key=f"cv_parse:{cv_hash}",
        file=attachment_data,
    )
    logger.debug("Queued pipeline for %s (submission %s)", filename, submission.id)
    return "queued"
