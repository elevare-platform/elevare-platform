"""Unit tests for ingestion Celery task helpers.

Pure logic tests only — no DB, no Celery broker. Covers the token-refresh
retry wrappers (added after a production historical import hit a 401 when
the OAuth access token expired mid-run) and the provider→source mapping
used to correctly label Gmail vs Zoho imports in the talent pool.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from app.modules.ingestion.tasks import (
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
