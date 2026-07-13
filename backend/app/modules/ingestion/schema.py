"""Pydantic schemas for the ingestion module API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class GmailConnectResponse(BaseModel):
    """Returned when the user initiates Gmail OAuth."""

    auth_url: str
    message: str = "Redirect the user to auth_url to connect their Gmail account"


class IntegrationResponse(BaseModel):
    """Safe representation of a MailIntegration — no tokens exposed."""

    id: uuid.UUID
    provider: str
    status: str
    email_address: str | None
    last_synced_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TriggerImportRequest(BaseModel):
    """Optional body for POST /import/trigger."""

    query_filter: str | None = Field(
        default=None,
        description=(
            "Gmail search query to scope the import. "
            "Defaults to: has:attachment (all emails with attachments). "
            "Example to scope by date: has:attachment after:2022/01/01"
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
