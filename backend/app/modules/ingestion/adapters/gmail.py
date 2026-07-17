"""Gmail adapter — implements MailAdapter using the Gmail REST API over httpx.

No google-api-python-client dependency. Pure async httpx calls so this fits
naturally into the existing async/await codebase.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import UTC, datetime

import httpx

from app.modules.ingestion.adapters.base import MailAdapter, MailAttachment, MailMessage

logger = logging.getLogger(__name__)

_GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

# Scopes required — readonly is sufficient, we never send or delete
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "email",
]


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Return the Google OAuth2 authorisation URL to redirect the user to."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",  # gets us a refresh token
        "prompt": "consent",  # forces refresh token even if previously granted
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{_AUTH_URL}?{query}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange an authorisation code for access + refresh tokens.

    Returns the raw token response dict from Google:
    {access_token, refresh_token, expires_in, token_type, scope}
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Use a refresh token to get a new access token.

    Returns {access_token, expires_in, token_type, scope}.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
            },
        )
        resp.raise_for_status()
        return resp.json()


def _extract_email_address(sender: str) -> str:
    """Pull the plain email address out of 'Name <email>' or return as-is."""
    match = re.search(r"<([^>]+)>", sender)
    return match.group(1).lower() if match else sender.lower().strip()


def _decode_body(data: str) -> bytes:
    """Base64url-decode a Gmail message body part."""
    # Gmail uses URL-safe base64 without padding — fix it
    padded = data.replace("-", "+").replace("_", "/")
    padded += "=" * (-len(padded) % 4)
    return base64.b64decode(padded)


def _get_header(headers: list[dict], name: str) -> str:
    """Extract a header value by name from a Gmail message headers list."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_gmail_message(raw: dict) -> tuple[dict, list[dict]]:
    """Walk the MIME tree and return (body_parts, attachment_parts).

    Returns a tuple:
      - body_snippet: plain-text snippet from Gmail's built-in snippet
      - attachments: list of {filename, mime_type, attachment_id, data, size}
    """
    attachments: list[dict] = []
    body_snippet = raw.get("snippet", "")

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        filename = part.get("filename", "")

        if filename and body.get("size", 0) > 0:
            attachments.append(
                {
                    "filename": filename,
                    "mime_type": mime,
                    "attachment_id": body.get("attachmentId"),
                    "data": body.get("data"),  # inline data if small enough
                    "size": body.get("size", 0),
                }
            )
        for sub in part.get("parts", []):
            walk(sub)

    walk(raw.get("payload", {}))
    return body_snippet, attachments


class GmailAdapter(MailAdapter):
    """Gmail REST API adapter.

    Instantiated per-request with a valid access token. Token refresh is
    handled by the IngestionService before constructing this adapter.

    Args:
        access_token: A valid (not expired) Gmail access token.
        user_email:   The mailbox email address (used as userId in API calls).
    """

    def __init__(self, access_token: str, user_email: str = "me") -> None:
        self._token = access_token
        self._user = user_email
        self._base = f"{_GMAIL_API}/users/{user_email}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def set_access_token(self, access_token: str) -> None:
        self._token = access_token

    async def list_messages(
        self,
        query: str = "",
        max_results: int = 500,
        page_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return a page of message IDs matching the query."""
        params: dict = {"maxResults": min(max_results, 500)}
        if query:
            params["q"] = query
        if page_token:
            params["pageToken"] = page_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/messages",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        ids = [m["id"] for m in data.get("messages", [])]
        next_token = data.get("nextPageToken")
        return ids, next_token

    async def get_message(self, message_id: str) -> MailMessage:
        """Fetch a full message and normalise it into a MailMessage."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/messages/{message_id}",
                headers=self._headers(),
                params={"format": "full"},
            )
            resp.raise_for_status()
            raw = resp.json()

        headers = raw.get("payload", {}).get("headers", [])
        subject = _get_header(headers, "Subject")
        sender = _get_header(headers, "From")
        sender_email = _extract_email_address(sender)

        # Gmail internalDate is milliseconds since epoch
        internal_date_ms = int(raw.get("internalDate", 0))
        received_at = datetime.fromtimestamp(internal_date_ms / 1000, tz=UTC)

        body_snippet, raw_attachments = _parse_gmail_message(raw)

        # Fetch attachment bytes — download each one individually
        attachments: list[MailAttachment] = []
        async with httpx.AsyncClient(timeout=60) as client:
            for att in raw_attachments:
                if att["data"]:
                    # Inline data (small attachments)
                    data = _decode_body(att["data"])
                else:
                    # Large attachment — fetch from the attachments endpoint
                    att_resp = await client.get(
                        f"{self._base}/messages/{message_id}/attachments/{att['attachment_id']}",
                        headers=self._headers(),
                    )
                    att_resp.raise_for_status()
                    data = _decode_body(att_resp.json().get("data", ""))

                attachments.append(
                    MailAttachment(
                        filename=att["filename"],
                        content_type=att["mime_type"],
                        data=data,
                        size=att["size"],
                    )
                )

        return MailMessage(
            message_id=message_id,
            subject=subject,
            sender=sender,
            sender_email=sender_email,
            received_at=received_at,
            body_snippet=body_snippet[:300],
            attachments=attachments,
        )

    async def get_history_since(
        self,
        start_history_id: str,
    ) -> tuple[list[str], str]:
        """Return message IDs added since a historyId and the new cursor.

        Used for Phase 16B continuous sync.
        """
        params = {
            "startHistoryId": start_history_id,
            "historyTypes": "messageAdded",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/history",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        new_ids: list[str] = []
        for record in data.get("history", []):
            for added in record.get("messagesAdded", []):
                new_ids.append(added["message"]["id"])

        new_cursor = str(data.get("historyId", start_history_id))
        return new_ids, new_cursor

    async def get_current_history_id(self) -> str:
        """Return the current historyId — used to seed the sync cursor after import."""
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base}/profile",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return str(resp.json().get("historyId", ""))
