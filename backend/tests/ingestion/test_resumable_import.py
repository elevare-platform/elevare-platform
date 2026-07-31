"""Tests for the resumable-import checkpoint/handoff mechanism.

A production import got SIGKILLed by Celery's own hard time_limit after
running for the full 2 hours on a large mailbox — even with concurrent
message fetching, a big enough mailbox can still exceed any fixed time
budget. A hard kill bypasses all of the task's own cleanup code (same
failure mode as the stale-run incident, different trigger), leaving the
run stuck.

Rather than just raising the time limit (which only postpones the same
problem and, worse, ties up a worker slot even longer — the opposite of
what's needed to let many employers' imports interleave), a run now
checkpoints itself well before the hard limit and hands off to a fresh
task execution, which resumes from the persisted pagination cursor and
counts instead of restarting the whole mailbox from page one.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from app.modules.ingestion import service as ingestion_service_module
from app.modules.ingestion import tasks as ingestion_tasks
from app.modules.ingestion.enums import ImportStatus, IntegrationStatus, MailProvider
from app.modules.ingestion.models import IngestionImportRun, MailIntegration
from app.modules.ingestion.repository import IngestionRepository

from ..conftest import make_user


class _SameSessionCM:
    """Async context manager that hands back the test's own db_session
    instead of a new one — _run_import_async normally opens its own engine/
    connection (correct for a real worker process), but that means it can
    never see data set up via the db_session fixture's own uncommitted
    transaction. Patched in via async_sessionmaker below so the whole test
    runs on one connection, same as the other ingestion service tests."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _patch_run_import_to_use_test_session(monkeypatch, db_session):
    monkeypatch.setattr(
        ingestion_tasks,
        "create_async_engine",
        lambda *a, **k: AsyncMock(dispose=AsyncMock()),
    )
    monkeypatch.setattr(
        ingestion_tasks,
        "async_sessionmaker",
        lambda *a, **k: (lambda: _SameSessionCM(db_session)),
    )


async def _make_connected_integration(db_session, **overrides) -> MailIntegration:
    user = make_user()
    db_session.add(user)
    await db_session.flush()

    defaults = {
        "user_id": user.id,
        "provider": MailProvider.ZOHO.value,
        "status": IntegrationStatus.CONNECTED.value,
        "email_address": "careershub@elevare.com.ng|123",
        "encrypted_access_token": "stub",
        "encrypted_refresh_token": "stub",
        "token_expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    defaults.update(overrides)
    integration = MailIntegration(**defaults)
    db_session.add(integration)
    await db_session.flush()
    return integration


async def _make_run(db_session, integration_id, **overrides) -> IngestionImportRun:
    defaults = {
        "integration_id": integration_id,
        "status": ImportStatus.PENDING.value,
        "query_filter": "has:attachment",
    }
    defaults.update(overrides)
    run = IngestionImportRun(**defaults)
    db_session.add(run)
    await db_session.flush()
    return run


def _no_attachment_message(message_id: str):
    from app.modules.ingestion.adapters.base import MailMessage

    return MailMessage(
        message_id=message_id,
        subject="No CV here",
        sender="a@b.com",
        sender_email="a@b.com",
        received_at=datetime.now(UTC),
        attachments=[],
    )


@pytest.mark.asyncio
async def test_run_checkpoints_and_requeues_before_hard_time_limit(
    db_session, monkeypatch
):
    """Once the per-execution deadline is exceeded, the run must persist
    its resume cursor, hand off to a new task execution (same run_id),
    and exit cleanly — status stays RUNNING, not FAILED/COMPLETED."""
    monkeypatch.setattr(ingestion_tasks, "_TASK_DEADLINE_SECONDS", -1)
    _patch_run_import_to_use_test_session(monkeypatch, db_session)

    integration = await _make_connected_integration(db_session)
    run = await _make_run(db_session, integration.id)

    adapter = AsyncMock()
    adapter.list_messages.return_value = (["m1"], "next-page-token")
    adapter.get_message.side_effect = lambda mid: _no_attachment_message(mid)

    monkeypatch.setattr(
        ingestion_service_module.IngestionService, "get_valid_adapter", AsyncMock(return_value=adapter)
    )
    monkeypatch.setattr(
        ingestion_service_module.IngestionService, "ensure_fresh_token", AsyncMock()
    )
    requeue = Mock()
    monkeypatch.setattr(ingestion_tasks.run_historical_import_task, "delay", requeue)

    await ingestion_tasks._run_import_async(str(run.id), str(integration.id))

    repo = IngestionRepository(db_session)
    refreshed = await repo.get_import_run(run.id)

    assert refreshed.status == ImportStatus.RUNNING.value
    assert refreshed.resume_page_token == "next-page-token"
    assert refreshed.emails_skipped == 1  # the one no-attachment message
    requeue.assert_called_once_with(str(run.id), str(integration.id), None)


@pytest.mark.asyncio
async def test_run_resumes_from_persisted_cursor_and_counts(db_session, monkeypatch):
    """A run picking back up after a checkpoint must continue from the
    saved page_token and accumulate onto the already-persisted counts,
    not restart the mailbox scan from page one with counters at zero."""
    monkeypatch.setattr(ingestion_tasks, "_TASK_DEADLINE_SECONDS", 60 * 60)
    _patch_run_import_to_use_test_session(monkeypatch, db_session)

    integration = await _make_connected_integration(db_session)
    run = await _make_run(
        db_session,
        integration.id,
        status=ImportStatus.RUNNING.value,
        started_at=datetime.now(UTC) - timedelta(minutes=95),
        total_emails_found=50,
        emails_skipped=50,
        resume_page_token="resume-from-here",
    )

    adapter = AsyncMock()
    # Only one more page, then done — proves it didn't restart from page one
    adapter.list_messages.return_value = (["m2"], None)
    adapter.get_message.side_effect = lambda mid: _no_attachment_message(mid)
    adapter.get_current_history_id = AsyncMock(return_value="cursor-1")

    monkeypatch.setattr(
        ingestion_service_module.IngestionService, "get_valid_adapter", AsyncMock(return_value=adapter)
    )
    monkeypatch.setattr(
        ingestion_service_module.IngestionService, "ensure_fresh_token", AsyncMock()
    )

    await ingestion_tasks._run_import_async(str(run.id), str(integration.id))

    adapter.list_messages.assert_awaited_once()
    _, kwargs = adapter.list_messages.await_args
    assert kwargs["page_token"] == "resume-from-here"

    repo = IngestionRepository(db_session)
    refreshed = await repo.get_import_run(run.id)

    assert refreshed.status == ImportStatus.COMPLETED.value
    assert refreshed.total_emails_found == 51  # 50 already-persisted + 1 new
    assert refreshed.emails_skipped == 51
    assert refreshed.resume_page_token is None
    # started_at must not have been overwritten by this resumed execution
    assert refreshed.started_at < datetime.now(UTC) - timedelta(minutes=90)
