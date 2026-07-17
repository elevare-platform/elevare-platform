"""Zoho Mail adapter — implements MailAdapter using the Zoho Mail REST API over httpx.

Sync cursor strategy:
  We use the receivedTime (epoch milliseconds) of the newest message seen
  as the cursor. On each sync, we fetch messages received after that timestamp.

Message ID encoding:
  Zoho requires folderId in the URL to fetch a message:
    GET /accounts/{accountId}/folders/{folderId}/messages/{messageId}/details
  The list endpoint returns both messageId and folderId per message.
  We encode them as "folderId|messageId" in the returned ID list so get_message
  can unpack both values without changing the MailAdapter interface.

Per-message data is split across three separate Zoho endpoints — a single
message is NOT fully described by any one of them:
  /details        → subject, fromAddress, receivedTime, summary, hasAttachment
  /attachmentinfo → the real attachment list (attachmentId/attachmentName/attachmentSize)
  /content        → HTML body only ({messageId, content} — nothing else)
get_message() uses /details + /attachmentinfo. It deliberately does not call
/content — CV ingestion never needs the HTML body, only the metadata and the
attachments.
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
        self._folder_lookup_done: bool = False

    def _headers(self) -> dict:
        return {"Authorization": f"Zoho-oauthtoken {self._token}"}

    def set_access_token(self, access_token: str) -> None:
        self._token = access_token

    async def _get_inbox_folder_id(self) -> str | None:
        """Fetch and cache the Inbox folder ID.

        Requires ZohoMail.folders.READ scope.
        Falls back to None (all folders) if unavailable. The lookup is
        attempted at most once per adapter instance — without this, a
        historical import that pages through the mailbox re-issues this
        call (and, on a missing-scope account, re-fails it) on every
        single page, adding a wasted round trip per page for the entire
        run.
        """
        if self._folder_lookup_done:
            return self._inbox_folder_id
        self._folder_lookup_done = True
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
        return self._inbox_folder_id

    async def list_messages(
        self,
        query: str = "",
        max_results: int = 200,
        page_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return packed "folderId|messageId" strings, Inbox only if possible.

        When `query` is supplied (the caller always passes at least
        "has:attachment" — see IngestionService.trigger_historical_import),
        this hits Zoho's Search Emails endpoint so the filter is applied
        server-side. Zoho's search syntax uses the same operator names as
        Gmail's for what we need ("has:attachment", "after:", "before:",
        "subject:", "from:"), so the query string that already works for
        Gmail works here unchanged.

        Without this, `query` was silently ignored and every page paged
        through the *entire* mailbox (every folder, if the Inbox lookup
        failed) before filtering for attachments client-side — the cause
        of historical imports scanning far more messages than necessary.
        """
        start = int(page_token) if page_token else 0
        inbox_id = await self._get_inbox_folder_id()
        limit = min(max_results, 200)

        params: dict = {"start": start, "limit": limit}

        if query:
            params["searchKey"] = query
            if inbox_id:
                params["folderId"] = inbox_id
            url = f"{self._base}/messages/search"
        elif inbox_id:
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

        next_token = str(start + len(messages)) if len(messages) == limit else None
        return packed_ids, next_token

    async def get_message(self, message_id: str) -> MailMessage:
        """Fetch message metadata + attachments using the correct Zoho URLs.

        message_id is "folderId|zohoMessageId" as packed by list_messages.
        Zoho returns 500 on some messages (deleted, corrupted, spam-filtered).
        These are re-raised so the caller can count them as failed and move on.

        Pulls from /details (metadata) and, only if hasAttachment says so,
        /attachmentinfo (the real attachment list) — see the module
        docstring for why /content alone can't provide this.
        """
        if "|" in message_id:
            folder_id, zoho_msg_id = message_id.split("|", 1)
        else:
            raise ValueError(
                f"ZohoAdapter: message_id '{message_id}' missing folderId prefix"
            )

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/folders/{folder_id}/messages/{zoho_msg_id}/details",
                headers=self._headers(),
            )
            # 500 from Zoho = message is inaccessible (deleted, corrupt, spam)
            # Raise so the import loop counts it as failed and skips it cleanly
            resp.raise_for_status()
            raw = resp.json().get("data", {})

        # Zoho can send an explicit JSON null (not just an absent key) for
        # these fields on some system-generated messages — `.get(k, "")`
        # doesn't guard against that, so use `or ""` to normalise None too.
        subject = raw.get("subject") or ""
        sender = raw.get("fromAddress") or ""
        sender_email = _extract_email_address(sender)

        received_time_ms = int(raw.get("receivedTime") or 0)
        received_at = datetime.fromtimestamp(received_time_ms / 1000, tz=UTC)

        body_snippet = (raw.get("summary") or "")[:300]

        attachments: list[MailAttachment] = []
        if str(raw.get("hasAttachment", "0")) == "1":
            attachment_meta = await self._get_attachment_info(folder_id, zoho_msg_id)
            attachments = await self._fetch_attachments(
                folder_id, zoho_msg_id, attachment_meta
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

    async def _get_attachment_info(self, folder_id: str, message_id: str) -> list[dict]:
        """Fetch the real attachment list (attachmentId/Name/Size) for a message.

        Zoho serves this from a dedicated endpoint, separate from both
        /details and /content. A failure here doesn't fail the whole
        message — it just leaves it with no attachments, same as any
        other per-attachment download failure in _fetch_attachments.
        """
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self._base}/folders/{folder_id}/messages/{message_id}/attachmentinfo",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json().get("data", {}).get("attachments", [])
        except Exception:
            logger.warning(
                "ZohoAdapter: failed to fetch attachment info for message %s",
                message_id,
                exc_info=True,
            )
            return []

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
                        headers={
                            **self._headers(),
                            "Accept": "application/octet-stream",
                        },
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
        """Return packed "folderId|messageId" strings received after the cursor, Inbox only.

        Zoho's `receivedTime` request parameter filters for messages
        received *before* that timestamp (and only on the Search Emails
        endpoint — `/messages/view` doesn't document it at all), so it
        can't be used directly to express "since". Instead we fetch the
        newest page (server-side filtered to attachment-bearing messages
        via searchKey) and drop anything at or before the cursor
        ourselves. This also fixes continuous sync re-scanning the same
        ~200 most recent messages on every 15-minute poll.
        """
        since_ms = int(start_history_id)
        inbox_id = await self._get_inbox_folder_id()
        params: dict = {"start": 0, "limit": 200, "searchKey": "has:attachment"}
        if inbox_id:
            params["folderId"] = inbox_id

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{self._base}/messages/search", headers=self._headers(), params=params
            )
            resp.raise_for_status()
            data = resp.json()

        messages = data.get("data", [])
        new_ids: list[str] = []
        newest_ms = since_ms
        for m in messages:
            try:
                received = int(m.get("receivedTime", 0))
            except (TypeError, ValueError):
                continue
            if received <= since_ms:
                continue
            newest_ms = max(newest_ms, received)
            if str(m.get("hasAttachment", "0")) == "1" and m.get("messageId"):
                new_ids.append(f"{m.get('folderId', inbox_id or '')}|{m['messageId']}")

        new_cursor = str(newest_ms) if messages else start_history_id
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
