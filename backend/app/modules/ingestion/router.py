"""FastAPI router for the candidate ingestion module.

Endpoints:
  GET  /connect/gmail              — initiate OAuth flow, returns auth URL
  GET  /callback/gmail             — OAuth callback, stores tokens
  POST /integrations/{id}/import   — trigger historical import
  GET  /integrations/{id}/runs/{run_id} — poll import status
  GET  /integrations               — list user's integrations
  DELETE /integrations/{id}        — disconnect an integration
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.storage import get_storage_service
from app.modules.ingestion.schema import (
    GmailConnectResponse,
    ImportRunResponse,
    IntegrationResponse,
    TriggerImportRequest,
)
from app.modules.ingestion.service import IngestionService
from app.modules.users.enums import UserRole
from app.modules.users.models import User

router = APIRouter()


def _require_admin_or_employer(current_user: User = Depends(get_current_user)) -> User:
    """Only admins and employers can manage mail integrations."""
    if current_user.role not in (UserRole.ADMIN.value, UserRole.EMPLOYER.value):
        from app.core.exceptions import PermissionDeniedException

        raise PermissionDeniedException()
    return current_user


def _get_service(db: AsyncSession = Depends(get_db)) -> IngestionService:
    return IngestionService(db=db, storage=get_storage_service())


# ------------------------------------------------------------------ #
# OAuth
# ------------------------------------------------------------------ #


@router.get("/connect/gmail", response_model=GmailConnectResponse)
async def connect_gmail(
    current_user: User = Depends(_require_admin_or_employer),
    service: IngestionService = Depends(_get_service),
):
    """Initiate Gmail OAuth2 flow. Returns the URL to redirect the user to."""
    auth_url = service.get_gmail_auth_url(current_user.id)
    return GmailConnectResponse(auth_url=auth_url)


@router.get("/connect/zoho", response_model=GmailConnectResponse)
async def connect_zoho(
    current_user: User = Depends(_require_admin_or_employer),
    service: IngestionService = Depends(_get_service),
):
    """Initiate Zoho Mail OAuth2 flow. Returns the URL to redirect the user to."""
    auth_url = service.get_zoho_auth_url(current_user.id)
    return GmailConnectResponse(
        auth_url=auth_url,
        message="Redirect the user to auth_url to connect their Zoho Mail account",
    )


@router.get("/callback/gmail")
async def gmail_callback(
    code: str = Query(..., description="OAuth authorisation code from Google"),
    state: str = Query(..., description="State parameter echoed back by Google"),
    service: IngestionService = Depends(_get_service),
):
    """OAuth callback — Google redirects here after the user approves.

    Stores the integration then redirects the browser back to the
    frontend mail ingestion page with a success indicator.
    """
    try:
        user_id = uuid.UUID(state.split(":")[0])
    except (ValueError, IndexError):
        return RedirectResponse(
            url=f"{settings.app_url}/employer/mail-ingestion?connected=error",
            status_code=302,
        )

    try:
        await service.handle_gmail_callback(
            code=code,
            state=state,
            requesting_user_id=user_id,
        )
    except Exception:
        return RedirectResponse(
            url=f"{settings.app_url}/employer/mail-ingestion?connected=error",
            status_code=302,
        )

    # Redirect back to the frontend — the page will reload integrations
    return RedirectResponse(
        url=f"{settings.app_url}/employer/mail-ingestion?connected=success",
        status_code=302,
    )


@router.get("/callback/zoho")
async def zoho_callback(
    code: str = Query(..., description="OAuth authorisation code from Zoho"),
    state: str = Query(..., description="State parameter echoed back by Zoho"),
    service: IngestionService = Depends(_get_service),
):
    """OAuth callback — Zoho redirects here after the user approves."""
    try:
        user_id = uuid.UUID(state.split(":")[0])
    except (ValueError, IndexError):
        return RedirectResponse(
            url=f"{settings.app_url}/employer/mail-ingestion?connected=error",
            status_code=302,
        )

    try:
        await service.handle_zoho_callback(
            code=code,
            state=state,
            requesting_user_id=user_id,
        )
    except Exception:
        return RedirectResponse(
            url=f"{settings.app_url}/employer/mail-ingestion?connected=error",
            status_code=302,
        )

    return RedirectResponse(
        url=f"{settings.app_url}/employer/mail-ingestion?connected=success",
        status_code=302,
    )


# ------------------------------------------------------------------ #
# Integrations
# ------------------------------------------------------------------ #


@router.get("/integrations", response_model=list[IntegrationResponse])
async def list_integrations(
    current_user: User = Depends(_require_admin_or_employer),
    service: IngestionService = Depends(_get_service),
):
    """List all mail integrations for the current user."""
    integrations = await service.get_integration_status(current_user.id)
    return [IntegrationResponse.model_validate(i) for i in integrations]


@router.delete("/integrations/{integration_id}", status_code=204)
async def disconnect_integration(
    integration_id: uuid.UUID,
    current_user: User = Depends(_require_admin_or_employer),
    service: IngestionService = Depends(_get_service),
):
    """Disconnect a mail integration and wipe its stored tokens."""
    await service.disconnect_integration(integration_id, current_user.id)


# ------------------------------------------------------------------ #
# Import
# ------------------------------------------------------------------ #


@router.post(
    "/integrations/{integration_id}/import",
    response_model=ImportRunResponse,
    status_code=202,
)
async def trigger_import(
    integration_id: uuid.UUID,
    body: TriggerImportRequest = TriggerImportRequest(),
    current_user: User = Depends(_require_admin_or_employer),
    service: IngestionService = Depends(_get_service),
):
    """Trigger a historical email import for a connected Gmail integration.

    Returns immediately with a run ID. Poll GET /runs/{run_id} for progress.
    """
    run = await service.trigger_historical_import(
        integration_id=integration_id,
        requesting_user_id=current_user.id,
        query_filter=body.query_filter,
        sourced_for_job_id=body.sourced_for_job_id,
    )
    return ImportRunResponse.model_validate(run)


@router.get(
    "/integrations/{integration_id}/runs/{run_id}",
    response_model=ImportRunResponse,
)
async def get_import_run(
    integration_id: uuid.UUID,
    run_id: uuid.UUID,
    current_user: User = Depends(_require_admin_or_employer),
    service: IngestionService = Depends(_get_service),
):
    """Poll the status of an import run."""
    run = await service.get_import_run_status(run_id, current_user.id)
    return ImportRunResponse.model_validate(run)
