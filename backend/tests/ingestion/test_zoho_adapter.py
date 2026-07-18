"""Unit tests for ZohoAdapter.

All HTTP calls are mocked — no real Zoho API calls made.
Tests verify that the adapter correctly parses Zoho Mail's JSON response shapes
and returns normalised MailMessage / MailAttachment dataclasses.

Key Zoho differences from Gmail tested here:
  - Auth header is "Zoho-oauthtoken" not "Bearer"
  - Pagination is index-based (start + limit) not cursor-based
  - Sync cursor is epoch milliseconds (receivedTime) not historyId
  - Account ID is required for API calls
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.modules.ingestion.adapters.zoho import (
    ZohoAdapter,
    _extract_email_address,
    build_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
)

# ─── Helper ───────────────────────────────────────────────────────────────────


def _make_mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    req = httpx.Request("GET", "https://mock.test/")
    return httpx.Response(status_code, json=json_data, request=req)


# ─── Pure helper tests ────────────────────────────────────────────────────────


def test_extract_email_with_name():
    assert _extract_email_address("Jane Doe <jane@zoho.com>") == "jane@zoho.com"


def test_extract_email_plain():
    assert _extract_email_address("jane@zoho.com") == "jane@zoho.com"


def test_build_auth_url_contains_scopes():
    url = build_auth_url(
        client_id="cid_123",
        redirect_uri="http://localhost/cb",
        state="state_xyz",
        accounts_url="https://accounts.zoho.com",
    )
    assert "cid_123" in url
    assert "ZohoMail.messages.READ" in url
    assert "state_xyz" in url
    assert "offline" in url
    assert "accounts.zoho.com" in url


def test_build_auth_url_uses_regional_domain():
    url = build_auth_url("cid", "http://cb", "state", "https://accounts.zoho.eu")
    assert "accounts.zoho.eu" in url


# ─── ZohoAdapter.list_messages ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_messages_returns_ids():
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    mock_json = {
        "data": [
            {"messageId": "zm1", "folderId": "f1", "hasAttachment": "1"},
            {"messageId": "zm2", "folderId": "f1", "hasAttachment": "1"},
            {"messageId": "zm3", "folderId": "f1", "hasAttachment": "1"},
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, next_token = await adapter.list_messages(max_results=3)

    # IDs are packed as "folderId|messageId"
    assert ids == ["f1|zm1", "f1|zm2", "f1|zm3"]
    assert next_token == "3"  # start(0) + count(3)


@pytest.mark.asyncio
async def test_list_messages_skips_no_attachment():
    """Messages without attachments are filtered out at list stage."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    mock_json = {
        "data": [
            {"messageId": "zm1", "folderId": "f1", "hasAttachment": "1"},
            {
                "messageId": "zm2",
                "folderId": "f1",
                "hasAttachment": "0",
            },  # no attachment
            {"messageId": "zm3", "folderId": "f1", "hasAttachment": "1"},
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, _ = await adapter.list_messages(max_results=10)

    assert ids == ["f1|zm1", "f1|zm3"]  # zm2 filtered out


@pytest.mark.asyncio
async def test_list_messages_last_page_no_next_token():
    """If fewer results than limit returned, it's the last page."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    mock_json = {
        "data": [{"messageId": "zm_only", "folderId": "f1", "hasAttachment": "1"}]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, next_token = await adapter.list_messages(max_results=200)

    assert next_token is None


@pytest.mark.asyncio
async def test_list_messages_empty():
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response({"data": []})
        ids, next_token = await adapter.list_messages()

    assert ids == []
    assert next_token is None


@pytest.mark.asyncio
async def test_list_messages_with_query_uses_search_endpoint():
    """A non-empty query (e.g. the "has:attachment" default from
    IngestionService) must hit Zoho's Search Emails endpoint with
    searchKey set, so filtering happens server-side instead of paging
    through the whole mailbox client-side."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    mock_json = {"data": [{"messageId": "zm1", "folderId": "f1", "hasAttachment": "1"}]}

    captured = {}

    async def mock_get(url, params=None, **kwargs):
        captured["url"] = str(url)
        captured["params"] = params
        return _make_mock_response(mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        ids, _ = await adapter.list_messages(query="has:attachment", max_results=500)

    assert "messages/search" in captured["url"]
    assert captured["params"]["searchKey"] == "has:attachment"
    assert ids == ["f1|zm1"]


@pytest.mark.asyncio
async def test_list_messages_without_query_uses_view_endpoint():
    """No query (e.g. get_current_history_id's raw listing) keeps using
    the plain List Emails endpoint — unchanged legacy behaviour."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    captured = {}

    async def mock_get(url, params=None, **kwargs):
        captured["url"] = str(url)
        return _make_mock_response({"data": []})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        await adapter.list_messages()

    assert "messages/search" not in captured["url"]
    assert "messages/view" in captured["url"]


@pytest.mark.asyncio
async def test_folder_lookup_attempted_only_once_per_adapter():
    """A failing (or successful) Inbox folder lookup must not be retried
    on every page — that turns one bad/slow call into one per page across
    a whole historical import."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    folder_calls = 0

    async def mock_get(url, **kwargs):
        nonlocal folder_calls
        if str(url).endswith("/folders"):
            folder_calls += 1
            raise httpx.HTTPError("no folder scope")
        return _make_mock_response({"data": []})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        await adapter.list_messages(query="has:attachment")
        await adapter.list_messages(query="has:attachment", page_token="200")
        await adapter.list_messages(query="has:attachment", page_token="400")

    assert folder_calls == 1


# ─── ZohoAdapter.get_message ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_message_no_attachment():
    """get_message reads metadata from /details — NOT /content, which per
    Zoho's real API only ever returns {messageId, content} and none of the
    fields this adapter needs (subject/fromAddress/receivedTime/summary/
    hasAttachment). Hitting /content there was the actual production bug:
    every message silently looked attachment-less."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    details_json = {
        "data": {
            "messageId": "zm99",
            "subject": "Hello there",
            "fromAddress": "sender@zoho.com",
            "receivedTime": "1720000000000",
            "summary": "Just a plain email",
            "hasAttachment": "0",
        }
    }

    captured_url = []

    async def mock_get(url, **kwargs):
        captured_url.append(str(url))
        return _make_mock_response(details_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm99")

    assert message.message_id == "f42|zm99"
    assert message.subject == "Hello there"
    assert message.sender_email == "sender@zoho.com"
    assert message.received_at == datetime.fromtimestamp(1720000000, tz=UTC)
    assert message.attachments == []
    # Verify the correct URL was used — /details, not /content
    assert "folders/f42/messages/zm99/details" in captured_url[0]
    # hasAttachment == "0" — must not even call /attachmentinfo
    assert not any("attachmentinfo" in u for u in captured_url)


@pytest.mark.asyncio
async def test_get_message_with_attachment():
    """hasAttachment=1 triggers /attachmentinfo (the real attachment list,
    separate from /details) followed by the actual binary download."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    pdf_bytes = b"%PDF-1.4 zoho test"

    details_json = {
        "data": {
            "messageId": "zm_att",
            "subject": "CV Application",
            "fromAddress": "candidate@example.com",
            "receivedTime": "1720000000000",
            "summary": "My CV is attached",
            "hasAttachment": "1",
        }
    }
    attachment_info_json = {
        "data": {
            "attachments": [
                {
                    "attachmentId": "att_zoho_1",
                    "attachmentName": "CV_Zoho.pdf",
                    "attachmentSize": str(len(pdf_bytes)),
                }
            ]
        }
    }

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "attachmentinfo" in str(url):
            return _make_mock_response(attachment_info_json)
        if "attachments/" in str(url):
            return httpx.Response(
                200, content=pdf_bytes, request=httpx.Request("GET", url)
            )
        return _make_mock_response(details_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm_att")

    assert call_count == 3  # details, attachmentinfo, attachment download
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "CV_Zoho.pdf"
    assert message.attachments[0].data == pdf_bytes


@pytest.mark.asyncio
async def test_get_message_attachment_download_failure_skipped():
    """A failed attachment download is logged and skipped — message still returned."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    details_json = {
        "data": {
            "messageId": "zm_fail",
            "subject": "CV",
            "fromAddress": "a@b.com",
            "receivedTime": "1720000000000",
            "summary": "",
            "hasAttachment": "1",
        }
    }
    attachment_info_json = {
        "data": {
            "attachments": [
                {
                    "attachmentId": "att_bad",
                    "attachmentName": "cv.pdf",
                    "attachmentSize": "1000",
                }
            ]
        }
    }

    async def mock_get(url, **kwargs):
        if "attachmentinfo" in str(url):
            return _make_mock_response(attachment_info_json)
        if "attachments/" in str(url):
            raise httpx.HTTPError("connection error")
        return _make_mock_response(details_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm_fail")

    assert message.message_id == "f42|zm_fail"
    assert message.attachments == []


@pytest.mark.asyncio
async def test_get_message_attachment_info_failure_yields_no_attachments():
    """If /attachmentinfo itself fails (network error, etc.), the message
    is still returned — just with no attachments — rather than failing
    the whole message fetch."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    details_json = {
        "data": {
            "messageId": "zm_info_fail",
            "subject": "CV",
            "fromAddress": "a@b.com",
            "receivedTime": "1720000000000",
            "summary": "",
            "hasAttachment": "1",
        }
    }

    async def mock_get(url, **kwargs):
        if "attachmentinfo" in str(url):
            raise httpx.HTTPError("connection error")
        return _make_mock_response(details_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm_info_fail")

    assert message.attachments == []


# ─── ZohoAdapter.get_history_since ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_history_since_returns_new_ids_and_advances_cursor():
    """Messages received after the cursor are returned with updated cursor."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    since_ms = "1720000000000"
    newer_ms = "1720001000000"

    mock_json = {
        "data": [
            {
                "messageId": "new_1",
                "folderId": "f1",
                "receivedTime": newer_ms,
                "hasAttachment": "1",
            },
            {
                "messageId": "new_2",
                "folderId": "f1",
                "receivedTime": "1720000500000",
                "hasAttachment": "1",
            },
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, new_cursor = await adapter.get_history_since(since_ms)

    assert ids == ["f1|new_1", "f1|new_2"]
    # Cursor advances to the most recent message's receivedTime
    assert new_cursor == newer_ms


@pytest.mark.asyncio
async def test_get_history_since_uses_search_endpoint():
    """get_history_since must use the Search Emails endpoint — the plain
    List Emails endpoint (/messages/view) doesn't support any timestamp
    filter, so using it made every 15-minute sync re-scan the same top
    ~200 messages instead of only genuinely new ones."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    captured = {}

    async def mock_get(url, params=None, **kwargs):
        captured["url"] = str(url)
        captured["params"] = params
        return _make_mock_response({"data": []})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        await adapter.get_history_since("1720000000000")

    assert "messages/search" in captured["url"]
    assert captured["params"]["searchKey"] == "has:attachment"


@pytest.mark.asyncio
async def test_get_history_since_filters_out_stale_messages():
    """Zoho has no server-side "received after" filter, so the adapter
    must drop messages at-or-before the cursor itself rather than trusting
    the API to have already excluded them."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    since_ms = "1720000000000"

    mock_json = {
        "data": [
            {
                "messageId": "already_seen",
                "folderId": "f1",
                "receivedTime": "1719999999999",  # before cursor
                "hasAttachment": "1",
            },
            {
                "messageId": "at_cursor",
                "folderId": "f1",
                "receivedTime": since_ms,  # exactly at cursor
                "hasAttachment": "1",
            },
            {
                "messageId": "genuinely_new",
                "folderId": "f1",
                "receivedTime": "1720000100000",
                "hasAttachment": "1",
            },
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, new_cursor = await adapter.get_history_since(since_ms)

    assert ids == ["f1|genuinely_new"]
    assert new_cursor == "1720000100000"


@pytest.mark.asyncio
async def test_get_history_since_no_new_messages_keeps_cursor():
    """If no new messages, cursor stays the same."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    since_ms = "1720000000000"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response({"data": []})
        ids, new_cursor = await adapter.get_history_since(since_ms)

    assert ids == []
    assert new_cursor == since_ms  # unchanged


# ─── ZohoAdapter.get_current_history_id ──────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_history_id_returns_latest_received_time():
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    mock_json = {"data": [{"messageId": "latest", "receivedTime": "1720999000000"}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        cursor = await adapter.get_current_history_id()

    assert cursor == "1720999000000"


@pytest.mark.asyncio
async def test_get_current_history_id_empty_mailbox_uses_now():
    """An empty mailbox returns current time as cursor so future syncs start now."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response({"data": []})
        cursor = await adapter.get_current_history_id()

    # Should be a large epoch-ms number close to now
    assert int(cursor) > 1_700_000_000_000


# ─── Token exchange functions ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_zoho_exchange_code_for_tokens():
    mock_response = {
        "access_token": "zoho_acc",
        "refresh_token": "zoho_ref",
        "expires_in": 3600,
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_mock_response(mock_response)
        result = await exchange_code_for_tokens(
            code="auth_code",
            client_id="cid",
            client_secret="csecret",
            redirect_uri="http://localhost/cb",
            accounts_url="https://accounts.zoho.com",
        )

    assert result["access_token"] == "zoho_acc"
    assert result["refresh_token"] == "zoho_ref"


@pytest.mark.asyncio
async def test_zoho_refresh_access_token():
    mock_response = {"access_token": "zoho_new_acc", "expires_in": 3600}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_mock_response(mock_response)
        result = await refresh_access_token(
            refresh_token="zoho_ref",
            client_id="cid",
            client_secret="csecret",
            accounts_url="https://accounts.zoho.com",
        )

    assert result["access_token"] == "zoho_new_acc"


@pytest.mark.asyncio
async def test_zoho_uses_correct_auth_header():
    """Zoho requires 'Zoho-oauthtoken' header — not 'Bearer'."""
    adapter = ZohoAdapter(access_token="my_zoho_token", account_id="acct_123")
    captured_headers = {}

    async def mock_get(url, headers=None, **kwargs):
        captured_headers.update(headers or {})
        return _make_mock_response({"data": []})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        await adapter.list_messages()

    assert captured_headers.get("Authorization") == "Zoho-oauthtoken my_zoho_token"
