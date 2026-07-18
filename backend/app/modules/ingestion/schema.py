"""Pydantic schemas for the ingestion module API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GmailConnectResponse(BaseModel):
    """Returned when the user initiates Gmail OAuth."""

    auth_url: str
    message: str = "Redirect the user to auth_url to connect their Gmail account"


class ImportRunResponse(BaseModel):
    """Current state of an import run."""

    id: uuid.UUID
    integration_id: uuid.UUID
    status: str
    total_emails_found: int
    emails_processed: int
    emails_skipped: int
    emails_failed: int
    emails_deduplicated: int
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    query_filter: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IntegrationResponse(BaseModel):
    """Safe representation of a MailIntegration — no tokens exposed."""

    id: uuid.UUID
    provider: str
    status: str
    email_address: str | None
    last_synced_at: datetime | None
    created_at: datetime
    # Most recent import run for this integration, if any — lets the
    # frontend show live/last-known progress on page load without the
    # user having to keep a browser tab open or remember a run id.
    latest_run: ImportRunResponse | None = None

    model_config = {"from_attributes": True}


class TriggerImportRequest(BaseModel):
    """Optional body for POST /import/trigger."""

    query_filter: str | None = Field(
        default=None,
        description=(
            "Search query to scope the import, in Gmail search syntax "
            "(also used as-is against Zoho Mail — the two share operator "
            "names for has:/subject:/from:/after:/before:, though date "
            "format differs: Gmail wants YYYY/MM/DD, Zoho wants YYYY-MM-DD). "
            "Defaults to: has:attachment (all emails with attachments)."
        ),
        examples=["has:attachment after:2022/01/01"],
    )
    sourced_for_job_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional job ID to score imported CVs against. "
            "If provided, imported candidates are added to that job's talent pool and scored. "
            "If omitted, CVs are parsed and added to the general talent pool unscored."
        ),
    )
