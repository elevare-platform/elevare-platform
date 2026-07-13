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

from app.modules.ingestion.adapters.base import MailAttachment, MailMessage
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


# ─── ZohoAdapter.get_message ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_message_no_attachment():
    """get_message uses correct folder-based URL and returns MailMessage."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    mock_json = {
        "data": {
            "messageId": "zm99",
            "subject": "Hello there",
            "fromAddress": "sender@zoho.com",
            "receivedTime": "1720000000000",
            "summary": "Just a plain email",
            "hasAttachment": "0",
            "attachments": [],
        }
    }

    captured_url = []

    async def mock_get(url, **kwargs):
        captured_url.append(str(url))
        return _make_mock_response(mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm99")

    assert message.message_id == "f42|zm99"
    assert message.subject == "Hello there"
    assert message.sender_email == "sender@zoho.com"
    assert message.received_at == datetime.fromtimestamp(1720000000, tz=UTC)
    assert message.attachments == []
    # Verify the correct URL was used
    assert "folders/f42/messages/zm99/content" in captured_url[0]


@pytest.mark.asyncio
async def test_get_message_with_attachment():
    """Message with attachment triggers a download using folder-based URL."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")
    pdf_bytes = b"%PDF-1.4 zoho test"

    message_json = {
        "data": {
            "messageId": "zm_att",
            "subject": "CV Application",
            "fromAddress": "candidate@example.com",
            "receivedTime": "1720000000000",
            "summary": "My CV is attached",
            "hasAttachment": "1",
            "attachments": [
                {
                    "attachmentId": "att_zoho_1",
                    "attachmentName": "CV_Zoho.pdf",
                    "attachmentType": "application/pdf",
                    "attachmentSize": str(len(pdf_bytes)),
                }
            ],
        }
    }

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "attachments" in str(url):
            return httpx.Response(
                200, content=pdf_bytes, request=httpx.Request("GET", url)
            )
        return _make_mock_response(message_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm_att")

    assert call_count == 2
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "CV_Zoho.pdf"
    assert message.attachments[0].data == pdf_bytes


@pytest.mark.asyncio
async def test_get_message_attachment_download_failure_skipped():
    """A failed attachment download is logged and skipped — message still returned."""
    adapter = ZohoAdapter(access_token="ztok", account_id="acct_123")

    message_json = {
        "data": {
            "messageId": "zm_fail",
            "subject": "CV",
            "fromAddress": "a@b.com",
            "receivedTime": "1720000000000",
            "summary": "",
            "hasAttachment": "1",
            "attachments": [
                {
                    "attachmentId": "att_bad",
                    "attachmentName": "cv.pdf",
                    "attachmentType": "application/pdf",
                    "attachmentSize": "1000",
                }
            ],
        }
    }

    async def mock_get(url, **kwargs):
        if "attachments" in str(url):
            raise httpx.HTTPError("connection error")
        return _make_mock_response(message_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("f42|zm_fail")

    assert message.message_id == "f42|zm_fail"
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
