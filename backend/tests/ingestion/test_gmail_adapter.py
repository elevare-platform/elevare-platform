"""Unit tests for GmailAdapter.

All HTTP calls are mocked with httpx.MockTransport — no real API calls made.
Tests verify that the adapter correctly parses Gmail's JSON response shapes
and returns the normalised MailMessage / MailAttachment dataclasses.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.modules.ingestion.adapters.base import MailAttachment, MailMessage
from app.modules.ingestion.adapters.gmail import (
    GmailAdapter,
    _decode_body,
    _extract_email_address,
    _get_header,
    build_auth_url,
    exchange_code_for_tokens,
    refresh_access_token,
)

# ─── Helper ───────────────────────────────────────────────────────────────────


def _b64url(data: bytes) -> str:
    """Base64url-encode bytes the way Gmail does (no padding)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _make_mock_response(json_data: dict, status_code: int = 200) -> httpx.Response:
    req = httpx.Request("GET", "https://mock.test/")
    resp = httpx.Response(status_code, json=json_data, request=req)
    return resp


# ─── Pure helper function tests ───────────────────────────────────────────────


def test_extract_email_address_with_name():
    assert _extract_email_address("John Doe <john@example.com>") == "john@example.com"


def test_extract_email_address_plain():
    assert _extract_email_address("john@example.com") == "john@example.com"


def test_extract_email_address_lowercases():
    assert _extract_email_address("JOHN@EXAMPLE.COM") == "john@example.com"


def test_decode_body_roundtrip():
    original = b"Hello, this is a test PDF attachment content"
    encoded = _b64url(original)
    assert _decode_body(encoded) == original


def test_decode_body_handles_padding():
    """Gmail omits base64 padding — _decode_body must add it back."""
    data = b"x" * 10  # length that produces unpadded base64
    encoded = base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    assert "=" not in encoded  # confirm no padding
    assert _decode_body(encoded) == data


def test_get_header_found():
    headers = [
        {"name": "Subject", "value": "CV Application"},
        {"name": "From", "value": "a@b.com"},
    ]
    assert _get_header(headers, "Subject") == "CV Application"


def test_get_header_case_insensitive():
    headers = [{"name": "SUBJECT", "value": "Test"}]
    assert _get_header(headers, "subject") == "Test"


def test_get_header_missing():
    assert _get_header([], "Subject") == ""


def test_build_auth_url_contains_required_params():
    url = build_auth_url("client_123", "http://localhost/cb", "state_abc")
    assert "client_123" in url
    assert "http://localhost/cb" in url
    assert "state_abc" in url
    assert "offline" in url  # access_type=offline
    assert "consent" in url  # prompt=consent
    assert "gmail.readonly" in url


# ─── GmailAdapter.list_messages ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_messages_returns_ids_and_next_token():
    adapter = GmailAdapter(access_token="tok", user_email="me")
    mock_json = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}],
        "nextPageToken": "tok_next",
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, next_token = await adapter.list_messages(
            query="has:attachment", max_results=10
        )

    assert ids == ["msg1", "msg2"]
    assert next_token == "tok_next"


@pytest.mark.asyncio
async def test_list_messages_no_next_token_on_last_page():
    adapter = GmailAdapter(access_token="tok", user_email="me")
    mock_json = {"messages": [{"id": "only_msg"}]}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, next_token = await adapter.list_messages()

    assert next_token is None


@pytest.mark.asyncio
async def test_list_messages_empty_mailbox():
    adapter = GmailAdapter(access_token="tok", user_email="me")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response({})
        ids, next_token = await adapter.list_messages()

    assert ids == []
    assert next_token is None


# ─── GmailAdapter.get_message ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_message_normalises_fields():
    """get_message correctly maps Gmail JSON to MailMessage."""
    adapter = GmailAdapter(access_token="tok", user_email="me")

    pdf_bytes = b"%PDF-1.4 test content"
    encoded_pdf = _b64url(pdf_bytes)

    raw_message = {
        "id": "msg123",
        "snippet": "Please find my CV attached",
        "internalDate": "1720000000000",  # ms
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Job Application — Senior Engineer"},
                {"name": "From", "value": "Jane Smith <jane@example.com>"},
            ],
            "parts": [
                {
                    "mimeType": "application/pdf",
                    "filename": "JaneSmith_CV.pdf",
                    "body": {
                        "attachmentId": None,
                        "data": encoded_pdf,
                        "size": len(pdf_bytes),
                    },
                }
            ],
        },
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(raw_message)
        message = await adapter.get_message("msg123")

    assert message.message_id == "msg123"
    assert message.subject == "Job Application — Senior Engineer"
    assert message.sender_email == "jane@example.com"
    assert message.body_snippet == "Please find my CV attached"
    assert message.received_at == datetime.fromtimestamp(1720000000, tz=UTC)
    assert len(message.attachments) == 1
    assert message.attachments[0].filename == "JaneSmith_CV.pdf"
    assert message.attachments[0].data == pdf_bytes


@pytest.mark.asyncio
async def test_get_message_fetches_large_attachment_by_id():
    """Attachments without inline data trigger a second API call."""
    adapter = GmailAdapter(access_token="tok", user_email="me")

    large_pdf = b"%PDF large content " * 100
    encoded = _b64url(large_pdf)

    raw_message = {
        "id": "msg_large",
        "snippet": "CV enclosed",
        "internalDate": "1720000000000",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Application"},
                {"name": "From", "value": "bob@example.com"},
            ],
            "parts": [
                {
                    "mimeType": "application/pdf",
                    "filename": "cv.pdf",
                    "body": {
                        "attachmentId": "att_id_abc",
                        "data": None,  # no inline data — must fetch separately
                        "size": len(large_pdf),
                    },
                }
            ],
        },
    }

    attachment_response = {"data": encoded}

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "attachments" in str(url):
            return _make_mock_response(attachment_response)
        return _make_mock_response(raw_message)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
        message = await adapter.get_message("msg_large")

    assert call_count == 2  # one for message, one for attachment
    assert message.attachments[0].data == large_pdf


# ─── GmailAdapter.get_history_since ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_history_since_returns_new_ids_and_cursor():
    adapter = GmailAdapter(access_token="tok", user_email="me")
    mock_json = {
        "history": [
            {"messagesAdded": [{"message": {"id": "new_msg_1"}}]},
            {"messagesAdded": [{"message": {"id": "new_msg_2"}}]},
        ],
        "historyId": "99999",
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, new_cursor = await adapter.get_history_since("12345")

    assert ids == ["new_msg_1", "new_msg_2"]
    assert new_cursor == "99999"


@pytest.mark.asyncio
async def test_get_history_since_no_new_messages():
    adapter = GmailAdapter(access_token="tok", user_email="me")
    mock_json = {"history": [], "historyId": "12346"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        ids, new_cursor = await adapter.get_history_since("12345")

    assert ids == []
    assert new_cursor == "12346"


# ─── GmailAdapter.get_current_history_id ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_history_id():
    adapter = GmailAdapter(access_token="tok", user_email="me")
    mock_json = {"historyId": "55555"}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = _make_mock_response(mock_json)
        cursor = await adapter.get_current_history_id()

    assert cursor == "55555"


# ─── Token exchange functions ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_exchange_code_for_tokens():
    mock_response = {
        "access_token": "acc_tok",
        "refresh_token": "ref_tok",
        "expires_in": 3600,
        "token_type": "Bearer",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_mock_response(mock_response)
        result = await exchange_code_for_tokens(
            code="auth_code",
            client_id="cid",
            client_secret="csecret",
            redirect_uri="http://localhost/cb",
        )

    assert result["access_token"] == "acc_tok"
    assert result["refresh_token"] == "ref_tok"


@pytest.mark.asyncio
async def test_refresh_access_token():
    mock_response = {"access_token": "new_acc_tok", "expires_in": 3600}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _make_mock_response(mock_response)
        result = await refresh_access_token(
            refresh_token="ref_tok",
            client_id="cid",
            client_secret="csecret",
        )

    assert result["access_token"] == "new_acc_tok"
