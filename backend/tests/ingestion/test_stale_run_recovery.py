"""Tests for orphaned-import-run recovery.

A production Zoho import got permanently stuck showing "RUNNING" for a
week — the celery worker running it evidently died mid-task (e.g. an OOM
kill or the task's own hard time_limit), which bypasses the task's own
except-block cleanup and leaves the run row stuck RUNNING forever. That
silently blocked all future imports (trigger_historical_import refuses to
start a second run while one is RUNNING/PENDING) and incremental sync
(which needs a sync_cursor only ever set on successful completion).

These tests cover the two-part fix: trigger_historical_import self-heals
a stale run instead of blocking forever, and the periodic reaper task
proactively marks orphaned runs failed even before the user tries again.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.modules.ingestion.enums import ImportStatus, IntegrationStatus, MailProvider
from app.modules.ingestion.models import IngestionImportRun, MailIntegration
from app.modules.ingestion.repository import IngestionRepository
from app.modules.ingestion.service import IngestionService

from ..conftest import make_user


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


async def _make_run(db_session, integration_id, *, status, updated_at) -> IngestionImportRun:
    # updated_at is passed explicitly at construction (rather than relying on
    # server_default + a follow-up update) so the staleness check has a
    # controllable timestamp without fighting the column's onupdate=func.now().
    run = IngestionImportRun(
        integration_id=integration_id,
        status=status,
        total_emails_found=200,
        emails_processed=1293,
        updated_at=updated_at,
    )
    db_session.add(run)
    await db_session.flush()
    return run


@pytest.mark.asyncio
async def test_trigger_import_self_heals_stale_running_run(db_session, monkeypatch):
    """A RUNNING run untouched for >3h must not block a new import forever —
    it should be marked FAILED automatically and the new import allowed."""
    from app.modules.ingestion import tasks as ingestion_tasks

    monkeypatch.setattr(
        ingestion_tasks.run_historical_import_task, "delay", lambda *a, **k: None
    )

    integration = await _make_connected_integration(db_session)
    stale_run = await _make_run(
        db_session,
        integration.id,
        status=ImportStatus.RUNNING.value,
        updated_at=datetime.now(UTC) - timedelta(hours=4),
    )

    service = IngestionService(db_session, AsyncMock())
    new_run = await service.trigger_historical_import(
        integration_id=integration.id,
        requesting_user_id=integration.user_id,
    )

    assert new_run.id != stale_run.id
    repo = IngestionRepository(db_session)
    refreshed_stale = await repo.get_import_run(stale_run.id)
    assert refreshed_stale.status == ImportStatus.FAILED.value
    assert refreshed_stale.error_message


@pytest.mark.asyncio
async def test_trigger_import_still_blocks_a_genuinely_running_import(db_session):
    """A RUNNING run updated moments ago is a real in-progress import —
    must still be rejected with 409, not treated as orphaned."""
    from app.core.exceptions import PlatformError

    integration = await _make_connected_integration(db_session)
    await _make_run(
        db_session,
        integration.id,
        status=ImportStatus.RUNNING.value,
        updated_at=datetime.now(UTC),
    )

    service = IngestionService(db_session, AsyncMock())
    with pytest.raises(PlatformError):
        await service.trigger_historical_import(
            integration_id=integration.id,
            requesting_user_id=integration.user_id,
        )
