"""Unit tests for ingestion Celery task helpers.

Pure logic tests only — no DB, no Celery broker. Covers the token-refresh
retry wrappers (added after a production historical import hit a 401 when
the OAuth access token expired mid-run) and the provider→source mapping
used to correctly label Gmail vs Zoho imports in the talent pool.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import httpx
import pytest

from app.modules.ingestion.tasks import (
    _fetch_messages_concurrently,
    _get_message_with_refresh,
    _list_messages_with_refresh,
    _source_for_provider,
)

# ─── Helper ───────────────────────────────────────────────────────────────────


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://mock.test/")
    resp = httpx.Response(status_code, request=req)
    return httpx.HTTPStatusError("http error", request=req, response=resp)


# ─── _source_for_provider ─────────────────────────────────────────────────────


def test_source_for_provider_zoho():
    assert _source_for_provider("ZOHO") == ("zoho_import", "Zoho import")


def test_source_for_provider_gmail():
    assert _source_for_provider("GMAIL") == ("gmail_import", "Gmail import")


def test_source_for_provider_unknown_defaults_to_gmail():
    """Only ZOHO gets a distinct label — every other/unknown provider value
    (including empty) falls back to Gmail's, matching prior behaviour."""
    assert _source_for_provider("")[0] == "gmail_import"


# ─── _get_message_with_refresh ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_message_with_refresh_retries_once_on_401():
    """A 401 mid-import (expired access token) must trigger exactly one
    token refresh and one retry, not just be counted as a failed message."""
    adapter = AsyncMock()
    adapter.get_message.side_effect = [_http_error(401), "message-object"]
    service = AsyncMock()

    result = await _get_message_with_refresh(service, "integration-1", adapter, "msg-1")

    assert result == "message-object"
    service.ensure_fresh_token.assert_awaited_once_with("integration-1", adapter)
    assert adapter.get_message.await_count == 2


@pytest.mark.asyncio
async def test_get_message_with_refresh_reraises_non_401():
    """A non-auth error (e.g. Zoho's 500 for a corrupt message) must not
    trigger a pointless token refresh — it should propagate untouched."""
    adapter = AsyncMock()
    adapter.get_message.side_effect = _http_error(500)
    service = AsyncMock()

    with pytest.raises(httpx.HTTPStatusError):
        await _get_message_with_refresh(service, "integration-1", adapter, "msg-1")

    service.ensure_fresh_token.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_message_with_refresh_propagates_second_failure():
    """If the retry after refresh still fails, that failure propagates
    (the caller counts it as a genuine failed message)."""
    adapter = AsyncMock()
    adapter.get_message.side_effect = [_http_error(401), _http_error(401)]
    service = AsyncMock()

    with pytest.raises(httpx.HTTPStatusError):
        await _get_message_with_refresh(service, "integration-1", adapter, "msg-1")

    assert adapter.get_message.await_count == 2


# ─── _list_messages_with_refresh ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_messages_with_refresh_retries_once_on_401():
    adapter = AsyncMock()
    adapter.list_messages.side_effect = [_http_error(401), (["id1"], None)]
    service = AsyncMock()

    ids, token = await _list_messages_with_refresh(
        service, "integration-1", adapter, "has:attachment", 500, None
    )

    assert ids == ["id1"]
    assert token is None
    service.ensure_fresh_token.assert_awaited_once_with("integration-1", adapter)
    assert adapter.list_messages.await_count == 2


@pytest.mark.asyncio
async def test_list_messages_with_refresh_reraises_non_401():
    adapter = AsyncMock()
    adapter.list_messages.side_effect = _http_error(503)
    service = AsyncMock()

    with pytest.raises(httpx.HTTPStatusError):
        await _list_messages_with_refresh(
            service, "integration-1", adapter, "has:attachment", 500, None
        )

    service.ensure_fresh_token.assert_not_awaited()


# ─── _fetch_messages_concurrently ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_messages_concurrently_returns_results_in_order():
    """A single import's speed comes from fetching messages concurrently,
    not from how many other imports are running — results must still come
    back mapped to the right message_id, in the original order, regardless
    of which coroutine happened to finish first."""
    adapter = AsyncMock()

    async def get_message(message_id):
        # Reverse-ish completion order to prove ordering isn't accidental
        await asyncio.sleep({"a": 0.03, "b": 0.01, "c": 0.02}[message_id])
        return f"message-{message_id}"

    adapter.get_message.side_effect = get_message
    service = AsyncMock()

    results = await _fetch_messages_concurrently(
        service, "integration-1", adapter, ["a", "b", "c"]
    )

    assert [r[0] for r in results] == ["a", "b", "c"]
    assert [r[1] for r in results] == ["message-a", "message-b", "message-c"]
    assert all(r[2] is None for r in results)


@pytest.mark.asyncio
async def test_fetch_messages_concurrently_isolates_per_message_failures():
    """One message failing to fetch (deleted, corrupt, transient error)
    must not affect the others — it's reported back as that message's
    exception, not raised and lost."""
    adapter = AsyncMock()
    adapter.get_message.side_effect = [
        "message-a",
        _http_error(500),
        "message-c",
    ]
    service = AsyncMock()

    results = await _fetch_messages_concurrently(
        service, "integration-1", adapter, ["a", "b", "c"]
    )

    assert results[0] == ("a", "message-a", None)
    assert results[1][0] == "b"
    assert results[1][1] is None
    assert isinstance(results[1][2], httpx.HTTPStatusError)
    assert results[2] == ("c", "message-c", None)


@pytest.mark.asyncio
async def test_fetch_messages_concurrently_runs_in_parallel_not_sequentially():
    """The whole point of this helper — wall-clock time for N messages
    should be well under the fully-sequential worst case, or the semaphore
    is a no-op.

    _FETCH_CONCURRENCY=3 and _RATE_LIMIT_DELAY=0.15s means each fetch
    takes at least 0.15s. We use 3 messages so they all run in the first
    concurrency slot and complete in roughly one delay's worth of wall time.
    Sequential would take ~3 * 0.15s = 0.45s; concurrent should be close
    to one slot's worth. Generous upper bound to avoid CI flakiness.
    """
    adapter = AsyncMock()

    async def get_message(message_id):
        await asyncio.sleep(0.05)
        return message_id

    adapter.get_message.side_effect = get_message
    service = AsyncMock()

    # 3 messages == _FETCH_CONCURRENCY: all start in the first slot.
    # Sequential would take ~3 * 0.2s = 0.6s; concurrent completes in ~0.2s.
    message_ids = [str(i) for i in range(3)]
    start = time.monotonic()
    await _fetch_messages_concurrently(service, "integration-1", adapter, message_ids)
    elapsed = time.monotonic() - start

    assert elapsed < 0.45
