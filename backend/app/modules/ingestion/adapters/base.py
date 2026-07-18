from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MailAttachment:
    """A single attachment extracted from an email."""

    filename: str
    content_type: str
    data: bytes
    size: int


@dataclass
class MailMessage:
    """A normalised email message from any provider."""

    message_id: str  # provider's stable ID — stored for traceability
    subject: str
    sender: str  # "Name <email@domain.com>" or plain address
    sender_email: str  # extracted plain email address
    received_at: datetime
    body_snippet: str = ""  # first ~200 chars of body — used for keyword filtering
    attachments: list[MailAttachment] = field(default_factory=list)


class MailAdapter(ABC):
    """Abstract base for all mail provider adapters.

    Each provider (Gmail, Zoho, Outlook) implements this interface.
    The ingestion service only ever talks to this interface — adding a
    new provider is an adapter, not a service change.
    """

    @abstractmethod
    async def list_messages(
        self,
        query: str = "",
        max_results: int = 500,
        page_token: str | None = None,
    ) -> tuple[list[str], str | None]:
        """Return a page of message IDs and an optional next-page token.

        Args:
            query: Provider-specific search query (e.g. Gmail search syntax).
            max_results: Max IDs to return per page.
            page_token: Pagination cursor from a previous call.

        Returns:
            (message_ids, next_page_token) — next_page_token is None on last page.
        """

    @abstractmethod
    async def get_message(self, message_id: str) -> MailMessage:
        """Fetch and normalise a single message by its provider ID."""

    @abstractmethod
    async def get_history_since(
        self,
        start_history_id: str,
    ) -> tuple[list[str], str]:
        """Return new message IDs since a sync cursor and the new cursor value.

        Used for continuous sync (Phase 16B). Returns (new_message_ids, new_cursor).
        """

    @abstractmethod
    async def get_current_history_id(self) -> str:
        """Return the current sync cursor for this mailbox.

        Called once after a successful historical import to seed the
        continuous sync cursor.
        """

    @abstractmethod
    def set_access_token(self, access_token: str) -> None:
        """Swap in a freshly refreshed access token, in place.

        Historical imports can run for up to two hours while OAuth access
        tokens typically last about one — callers refresh mid-run by
        mutating the existing adapter rather than constructing a new one,
        so provider-side caches (e.g. ZohoAdapter's resolved inbox folder
        id) survive the refresh.
        """
