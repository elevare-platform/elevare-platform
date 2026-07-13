"""Zoho Mail adapter — implements MailAdapter using the Zoho Mail REST API over httpx.

Sync cursor strategy:
  We use the receivedTime (epoch milliseconds) of the newest message seen
  as the cursor. On each sync, we fetch messages received after that timestamp.

Message ID encoding:
  Zoho requires folderId in the URL to fetch message content:
    GET /accounts/{accountId}/folders/{folderId}/messages/{messageId}/content
  The list endpoint returns both messageId and folderId per message.
  We encode them as "folderId|messageId" in the returned ID list so get_message
  can unpack both values without changing the MailAdapter interface.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime

import httpx

from app.modules.ingestion.adapters.base import MailAdapter, MailAttachment, MailMessage

logger = logging.getLogger(__name__)

_TOKEN_PATH = "/oauth/v2/token"
_AUTH_PATH = "/oauth/v2/auth"

ZOHO_SCOPES = [
    "ZohoMail.messages.READ",
    "ZohoMail.accounts.READ",
    "ZohoMail.folders.READ",
]


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    accounts_url: str,
) -> str:
    """Return the Zoho OAuth2 authorisation URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": ",".join(ZOHO_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{accounts_url}{_AUTH_PATH}?{query}"


async def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    accounts_url: str,
) -> dict:
    """Exchange an authorisation code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{accounts_url}{_TOKEN_PATH}",
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
    accounts_url: str,
) -> dict:
    """Use a refresh token to get a new Zoho access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{accounts_url}{_TOKEN_PATH}",
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
    match = re.search(r"<([^>]+)>", sender)
    return match.group(1).lower() if match else sender.lower().strip()


class ZohoAdapter(MailAdapter):
    """Zoho Mail REST API adapter.

    Message IDs returned by list_messages are encoded as "folderId|messageId"
    so that get_message can construct the correct URL without an interface change.
    """

    def __init__(
        self,
        access_token: str,
        account_id: str,
        api_base_url: str = "https://mail.zoho.com/api",
    ) -> None:
        self._token = access_token
        self._account_id = account_id
        self._base = f"{api_base_url}/accounts/{account_id}"
        self._inbox_folder_id: str | None = None

    def _headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self._token}"}

    async def _get_inbox_folder_id(self) -> str | None:
        """Fetch and cache the Inbox folder ID.

        Requires ZohoMail.folders.READ scope.
        Falls back to None (all folders) if unavailable.
        """
        if self._inbox_folder_id:
            return self._inbox_folder_id
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base}/folders",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                for folder in resp.json().get("data", []):
                    name = str(folder.get("folderName", "")).lower()
                    ftype = str(folder.get("folderType", "")).lower()
                    if name == "inbox" or ftype == "inbox":
                        self._inbox_folder_id = str(folder["folderId"])
                        logger.info(
                            "ZohoAdapter: inbox folder = %s", self._inbox_folder_id
                        )
                        return self._inbox_folder_id
        except Exception:
            logger.warning(
                "ZohoAdapter: folder lookup failed — scanning all folders",
                exc_info=True,
            )
        return None

    async def list_messages(
        self,
        query: str = "",
        max_results: int = 200,
        page_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return packed "folderId|messageId" strings, Inbox only if possible."""
        start = int(page_token) if page_token else 0
        inbox_id = await self._get_inbox_folder_id()

        params: dict = {"start": start, "limit": min(max_results, 200)}

        if inbox_id:
            url = f"{self._base}/folders/{inbox_id}/messages/view"
        else:
            url = f"{self._base}/messages/view"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("data", [])
        packed_ids = [
            f"{m.get('folderId', inbox_id or '')}|{m['messageId']}"
            for m in messages
            if str(m.get("hasAttachment", "0")) == "1" and m.get("messageId")
        ]

        next_token = (
            str(start + len(messages)) if len(messages) == params["limit"] else None
        )
        return packed_ids, next_token

        next_token = (
            str(start + len(messages)) if len(messages) == params["limit"] else None
        )
        return packed_ids, next_token

    async def get_message(self, message_id: str) -> MailMessage:
        """Fetch message content using the correct Zoho URL structure.

        message_id is "folderId|zohoMessageId" as packed by list_messages.
        Zoho returns 500 on some messages (deleted, corrupted, spam-filtered).
        These are re-raised so the caller can count them as failed and move on.
        """
        if "|" in message_id:
            folder_id, zoho_msg_id = message_id.split("|", 1)
        else:
            raise ValueError(
                f"ZohoAdapter: message_id '{message_id}' missing folderId prefix"
            )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/folders/{folder_id}/messages/{zoho_msg_id}/content",
                headers=self._headers(),
            )
            # 500 from Zoho = message is inaccessible (deleted, corrupt, spam)
            # Raise so the import loop counts it as failed and skips it cleanly
            resp.raise_for_status()
            raw = resp.json().get("data", {})

        subject = raw.get("subject", "")
        sender = raw.get("fromAddress", "")
        sender_email = _extract_email_address(sender)

        received_time_ms = int(raw.get("receivedTime", 0))
        received_at = datetime.fromtimestamp(received_time_ms / 1000, tz=UTC)

        body_snippet = raw.get("summary", "")[:300]

        attachments: list[MailAttachment] = []
        if raw.get("hasAttachment") == "1" or raw.get("attachments"):
            attachments = await self._fetch_attachments(
                folder_id, zoho_msg_id, raw.get("attachments", [])
            )

        return MailMessage(
            message_id=message_id,  # keep the packed form for traceability
            subject=subject,
            sender=sender,
            sender_email=sender_email,
            received_at=received_at,
            body_snippet=body_snippet,
            attachments=attachments,
        )

    async def _fetch_attachments(
        self,
        folder_id: str,
        message_id: str,
        attachment_meta: list[dict],
    ) -> list[MailAttachment]:
        """Download all attachments for a message."""
        results: list[MailAttachment] = []

        async with httpx.AsyncClient(timeout=60) as client:
            for att in attachment_meta:
                att_id = att.get("attachmentId") or att.get("storeName")
                filename = att.get("attachmentName", "attachment")
                mime_type = att.get("attachmentType", "application/octet-stream")
                size = int(att.get("attachmentSize", 0))

                if not att_id:
                    continue

                try:
                    resp = await client.get(
                        f"{self._base}/folders/{folder_id}/messages/{message_id}/attachments/{att_id}",
                        headers=self._headers(),
                        params={"downloadType": "true"},
                    )
                    resp.raise_for_status()
                    data = resp.content
                except Exception:
                    logger.warning(
                        "ZohoAdapter: failed to download attachment %s from message %s",
                        att_id,
                        message_id,
                        exc_info=True,
                    )
                    continue

                results.append(
                    MailAttachment(
                        filename=filename,
                        content_type=mime_type,
                        data=data,
                        size=size or len(data),
                    )
                )

        return results

    async def get_history_since(
        self,
        start_history_id: str,
    ) -> tuple[list[str], str]:
        """Return packed "folderId|messageId" strings received after the cursor, Inbox only."""
        since_ms = int(start_history_id)
        inbox_id = await self._get_inbox_folder_id()
        params = {"start": 0, "limit": 200, "receivedTime": since_ms}

        if inbox_id:
            url = f"{self._base}/folders/{inbox_id}/messages/view"
        else:
            url = f"{self._base}/messages/view"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("data", [])
        new_ids = [
            f"{m.get('folderId', inbox_id or '')}|{m['messageId']}"
            for m in messages
            if str(m.get("hasAttachment", "0")) == "1" and m.get("messageId")
        ]
        new_cursor = (
            str(messages[0].get("receivedTime", since_ms))
            if messages
            else start_history_id
        )
        return new_ids, new_cursor

    async def get_current_history_id(self) -> str:
        """Return epoch ms of the most recent message as the sync cursor."""
        params = {"start": 0, "limit": 1}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self._base}/messages/view",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("data", [])
        if messages:
            return str(messages[0].get("receivedTime", ""))

        return str(int(datetime.now(UTC).timestamp() * 1000))
