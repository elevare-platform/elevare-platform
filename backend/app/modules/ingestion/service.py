"""Ingestion service — OAuth connect flow, token encryption, import orchestration.

This is the only layer that knows about both the mail adapter and the CV
parsing pipeline. Everything below it (parsing, scoring, talent pool) is
untouched — we just feed attachments into the existing submit_cv_for_parsing.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import StorageService
from app.modules.ingestion.adapters.gmail import GmailAdapter
from app.modules.ingestion.adapters.gmail import build_auth_url as gmail_build_auth_url
from app.modules.ingestion.adapters.gmail import (
    exchange_code_for_tokens as gmail_exchange_code,
)
from app.modules.ingestion.adapters.gmail import (
    refresh_access_token as gmail_refresh_token,
)
from app.modules.ingestion.adapters.zoho import ZohoAdapter
from app.modules.ingestion.adapters.zoho import build_auth_url as zoho_build_auth_url
from app.modules.ingestion.adapters.zoho import (
    exchange_code_for_tokens as zoho_exchange_code,
)
from app.modules.ingestion.adapters.zoho import (
    refresh_access_token as zoho_refresh_token,
)
from app.modules.ingestion.enums import ImportStatus, IntegrationStatus, MailProvider
from app.modules.ingestion.models import IngestionImportRun, MailIntegration
from app.modules.ingestion.repository import IngestionRepository

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Return a Fernet instance. Raises clearly if key is not configured."""
    if not settings.fernet_key:
        raise RuntimeError(
            "FERNET_KEY is not configured. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return Fernet(settings.fernet_key.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a plain-text token. Returns a hex-encoded ciphertext string."""
    return _get_fernet().encrypt(token.encode()).hex()


def decrypt_token(ciphertext_hex: str) -> str:
    """Decrypt a hex-encoded ciphertext back to the plain-text token."""
    try:
        return _get_fernet().decrypt(bytes.fromhex(ciphertext_hex)).decode()
    except (InvalidToken, ValueError) as e:
        raise ValueError("Token decryption failed — key may have rotated") from e


class IngestionService:
    """Orchestrates Gmail OAuth connection and historical import triggering.

    The actual import loop runs in a Celery task (tasks.py). This service
    handles the synchronous parts: OAuth handshake, token storage, and
    creating the import run record.
    """

    def __init__(
        self,
        db: AsyncSession,
        storage: StorageService,
    ) -> None:
        self._db = db
        self._storage = storage
        self._repo = IngestionRepository(db)

    # ------------------------------------------------------------------ #
    # OAuth — Gmail
    # ------------------------------------------------------------------ #

    def get_gmail_auth_url(self, user_id: uuid.UUID) -> str:
        """Build and return the Google OAuth2 authorisation URL."""
        if not settings.gmail_client_id:
            raise RuntimeError("GMAIL_CLIENT_ID is not configured")

        state = f"{user_id}:{secrets.token_urlsafe(16)}"
        return gmail_build_auth_url(
            client_id=settings.gmail_client_id,
            redirect_uri=settings.gmail_redirect_uri,
            state=state,
        )

    async def handle_gmail_callback(
        self,
        code: str,
        state: str,
        requesting_user_id: uuid.UUID,
    ) -> MailIntegration:
        """Exchange the Gmail OAuth code for tokens and persist the integration."""
        if not settings.gmail_client_id or not settings.gmail_client_secret:
            raise RuntimeError("Gmail OAuth credentials are not configured")

        token_data = await gmail_exchange_code(
            code=code,
            client_id=settings.gmail_client_id,
            client_secret=settings.gmail_client_secret,
            redirect_uri=settings.gmail_redirect_uri,
        )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        email_address = await self._get_gmail_email_address(access_token)

        enc_access = encrypt_token(access_token)
        enc_refresh = encrypt_token(refresh_token) if refresh_token else None

        integration = await self._repo.upsert_integration(
            user_id=requesting_user_id,
            provider=MailProvider.GMAIL,
            encrypted_access_token=enc_access,
            encrypted_refresh_token=enc_refresh,
            token_expires_at=token_expires_at,
            email_address=email_address,
        )
        await self._db.commit()
        logger.info(
            "Gmail integration connected for user %s → %s",
            requesting_user_id,
            email_address,
        )
        return integration

    async def _get_gmail_email_address(self, access_token: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/profile",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json().get("emailAddress", "unknown@gmail.com")

    # ------------------------------------------------------------------ #
    # OAuth — Zoho
    # ------------------------------------------------------------------ #

    def get_zoho_auth_url(self, user_id: uuid.UUID) -> str:
        """Build and return the Zoho OAuth2 authorisation URL."""
        if not settings.zoho_client_id:
            raise RuntimeError("ZOHO_CLIENT_ID is not configured")

        state = f"{user_id}:{secrets.token_urlsafe(16)}"
        return zoho_build_auth_url(
            client_id=settings.zoho_client_id,
            redirect_uri=settings.zoho_redirect_uri,
            state=state,
            accounts_url=settings.zoho_accounts_url,
        )

    async def handle_zoho_callback(
        self,
        code: str,
        state: str,
        requesting_user_id: uuid.UUID,
    ) -> list[MailIntegration]:
        """Exchange the Zoho OAuth code for tokens and persist one integration
        per Zoho Mail account found under this login.

        A single Zoho login can have multiple mail accounts (e.g. hr@, jobs@,
        careers@). We create a separate MailIntegration row for each so the
        user can see all of them on the page and disconnect the ones they don't
        want. The same access/refresh token pair is stored on every row — they
        all share the same OAuth grant.

        Returns the list of integrations created or updated.
        """
        if not settings.zoho_client_id or not settings.zoho_client_secret:
            raise RuntimeError("Zoho OAuth credentials are not configured")

        token_data = await zoho_exchange_code(
            code=code,
            client_id=settings.zoho_client_id,
            client_secret=settings.zoho_client_secret,
            redirect_uri=settings.zoho_redirect_uri,
            accounts_url=settings.zoho_accounts_url,
        )

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

        enc_access = encrypt_token(access_token)
        enc_refresh = encrypt_token(refresh_token) if refresh_token else None

        # Fetch all accounts under this Zoho login
        all_accounts = await self._get_all_zoho_accounts(access_token)

        if not all_accounts:
            raise ValueError("No Zoho Mail accounts found for this token")

        integrations: list[MailIntegration] = []
        for account_id, email_address in all_accounts:
            integration = await self._repo.upsert_integration(
                user_id=requesting_user_id,
                provider=MailProvider.ZOHO,
                encrypted_access_token=enc_access,
                encrypted_refresh_token=enc_refresh,
                token_expires_at=token_expires_at,
                # Pack "email|account_id" — unpacked in get_valid_adapter
                email_address=f"{email_address}|{account_id}",
            )
            integrations.append(integration)
            logger.info(
                "Zoho integration upserted for user %s → %s (account %s)",
                requesting_user_id,
                email_address,
                account_id,
            )

        await self._db.commit()
        return integrations

    async def _get_all_zoho_accounts(self, access_token: str) -> list[tuple[str, str]]:
        """Return a list of (account_id, email_address) for every Zoho Mail
        account under this OAuth token.

        Handles two known Zoho response shapes:
          Shape A: data is a list of account objects with accountId + emailAddress
          Shape B: data is a list of email alias dicts with isAlias/isPrimary/mailId
                   (seen on some Zoho configurations)
        """
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://mail.zoho.com/api/accounts",
                headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        raw_accounts = data.get("data", [])
        if not raw_accounts:
            return []

        results: list[tuple[str, str]] = []

        for item in raw_accounts:
            account_id = str(
                item.get("accountId") or item.get("accountid") or item.get("id") or ""
            )

            raw_email = (
                item.get("emailAddress")
                or item.get("emailId")
                or item.get("mailId")  # alias dict shape
                or ""
            )

            if isinstance(raw_email, list):
                # emailAddress is itself a list of alias objects
                primary = next(
                    (
                        e
                        for e in raw_email
                        if e.get("isPrimary") or not e.get("isAlias")
                    ),
                    raw_email[0] if raw_email else {},
                )
                email_address = (
                    primary.get("mailId") or primary.get("email") or "unknown@zoho.com"
                )
            else:
                email_address = str(raw_email) if raw_email else ""

            # Shape B: item itself is an alias dict (no accountId at top level)
            # In this case we need a separate call to get the real account ID
            if not account_id and email_address:
                # Use the email as a placeholder — the adapter will need the
                # real account ID. Try to resolve it.
                async with httpx.AsyncClient(timeout=10) as client2:
                    resp2 = await client2.get(
                        "https://mail.zoho.com/api/accounts",
                        headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
                        params={"type": "id"},
                    )
                    if resp2.status_code == 200:
                        id_items = resp2.json().get("data", [])
                        if id_items:
                            account_id = str(id_items[0].get("accountId", ""))

            if account_id and email_address:
                results.append((account_id, email_address))
            elif email_address:
                logger.warning(
                    "_get_all_zoho_accounts: could not resolve accountId for %s — skipping",
                    email_address,
                )

        return results

    # ------------------------------------------------------------------ #
    # Adapter factory — routes by provider
    # ------------------------------------------------------------------ #

    @staticmethod
    def _token_needs_refresh(integration: MailIntegration) -> bool:
        now = datetime.now(UTC)
        return (
            integration.token_expires_at is None
            or integration.token_expires_at <= now + timedelta(minutes=5)
        )

    async def get_valid_adapter(
        self, integration: MailIntegration
    ) -> GmailAdapter | ZohoAdapter:
        """Return the correct adapter with a fresh access token.

        Checks token expiry and refreshes silently if needed.
        Routes to GmailAdapter or ZohoAdapter based on integration.provider.
        """
        if self._token_needs_refresh(integration):
            if not integration.encrypted_refresh_token:
                raise ValueError(
                    f"Integration {integration.id} has no refresh token — user must reconnect"
                )
            access_token = await self._refresh_token(integration)
        else:
            access_token = decrypt_token(integration.encrypted_access_token)

        if integration.provider == MailProvider.ZOHO.value:
            # Unpack "email|account_id" stored during Zoho callback
            parts = (integration.email_address or "").split("|")
            account_id = parts[1] if len(parts) == 2 else parts[0]
            return ZohoAdapter(access_token=access_token, account_id=account_id)

        # Default: Gmail
        return GmailAdapter(
            access_token=access_token,
            user_email=(
                integration.email_address.split("|")[0]
                if integration.email_address
                else "me"
            ),
        )

    async def _refresh_token(self, integration: MailIntegration) -> str:
        """Refresh the access token for any provider. Returns the new access token."""
        refresh_tok = decrypt_token(integration.encrypted_refresh_token)

        if integration.provider == MailProvider.ZOHO.value:
            if not settings.zoho_client_id or not settings.zoho_client_secret:
                raise RuntimeError("Zoho OAuth credentials are not configured")
            new_data = await zoho_refresh_token(
                refresh_token=refresh_tok,
                client_id=settings.zoho_client_id,
                client_secret=settings.zoho_client_secret,
                accounts_url=settings.zoho_accounts_url,
            )
        else:
            if not settings.gmail_client_id or not settings.gmail_client_secret:
                raise RuntimeError("Gmail OAuth credentials are not configured")
            new_data = await gmail_refresh_token(
                refresh_token=refresh_tok,
                client_id=settings.gmail_client_id,
                client_secret=settings.gmail_client_secret,
            )

        new_access = new_data["access_token"]
        new_expires_at = datetime.now(UTC) + timedelta(
            seconds=new_data.get("expires_in", 3600)
        )

        await self._repo.update_integration(
            integration.id,
            {
                "encrypted_access_token": encrypt_token(new_access),
                "token_expires_at": new_expires_at,
                "status": IntegrationStatus.CONNECTED.value,
                "error_message": None,
            },
        )
        await self._db.commit()
        return new_access

    async def ensure_fresh_token(
        self,
        integration_id: uuid.UUID,
        adapter: GmailAdapter | ZohoAdapter,
    ) -> None:
        """Refresh the integration's token and swap it into `adapter` in place,
        if it's at or near expiry.

        Historical imports can run for up to two hours (see the Celery task's
        time_limit) while Gmail/Zoho access tokens typically last about an
        hour. Call this once per page of a long-running import loop, and
        again reactively on an actual 401, so a run doesn't spend the rest
        of its two hours failing every request after the token lapses.
        Mutating the existing adapter (rather than building a new one via
        get_valid_adapter) preserves adapter-local state such as
        ZohoAdapter's resolved inbox folder id.
        """
        integration = await self._repo.get_integration_by_id(integration_id)
        if not integration or not self._token_needs_refresh(integration):
            return
        if not integration.encrypted_refresh_token:
            raise ValueError(
                f"Integration {integration.id} has no refresh token — user must reconnect"
            )
        new_access_token = await self._refresh_token(integration)
        adapter.set_access_token(new_access_token)

    # ------------------------------------------------------------------ #
    # Import
    # ------------------------------------------------------------------ #

    async def trigger_historical_import(
        self,
        integration_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
        query_filter: str | None = None,
        sourced_for_job_id: uuid.UUID | None = None,
    ) -> IngestionImportRun:
        """Create an import run record and queue the Celery task.

        Returns immediately — the actual import runs in the background.
        Rejects if there's already a RUNNING or PENDING run for this integration.
        """
        from app.modules.ingestion.tasks import run_historical_import_task

        integration = await self._repo.get_integration_by_id(integration_id)
        if not integration:
            from app.core.exceptions import PlatformError

            raise PlatformError(
                "Integration not found", code="INTEGRATION_NOT_FOUND", status_code=404
            )

        if integration.user_id != requesting_user_id:
            from app.core.exceptions import PermissionDeniedException

            raise PermissionDeniedException()

        if integration.status != IntegrationStatus.CONNECTED.value:
            from app.core.exceptions import PlatformError

            raise PlatformError(
                f"Integration is not connected (status: {integration.status})",
                code="INTEGRATION_NOT_CONNECTED",
                status_code=400,
            )

        # Block double-trigger — only one active run per integration.
        # pg_advisory_xact_lock serialises concurrent callers on the same
        # integration for the rest of this transaction (auto-released on
        # commit/rollback below) — without it, two near-simultaneous
        # requests could both pass the "latest run" check before either
        # had created its row, and both create a RUNNING import.
        await self._db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"ingestion_import:{integration_id}"},
        )

        latest = await self._repo.get_latest_run_for_integration(integration_id)
        if latest and latest.status in (
            ImportStatus.RUNNING.value,
            ImportStatus.PENDING.value,
        ):
            from app.core.exceptions import PlatformError

            raise PlatformError(
                "An import is already running for this integration. "
                "Wait for it to complete before starting a new one.",
                code="INTEGRATION_ALREADY_RUNNING",
                status_code=409,
            )

        default_query = query_filter or "has:attachment"
        run = await self._repo.create_import_run(
            integration_id=integration_id,
            query_filter=default_query,
        )
        await self._db.commit()

        # Fire Celery task — passes IDs as strings (Celery JSON serialisation)
        run_historical_import_task.delay(
            str(run.id),
            str(integration_id),
            str(sourced_for_job_id) if sourced_for_job_id else None,
        )

        logger.info(
            "Historical import triggered for integration %s, run %s",
            integration_id,
            run.id,
        )
        return run

    # ------------------------------------------------------------------ #
    # Status / Read
    # ------------------------------------------------------------------ #

    async def get_integration_status(
        self,
        user_id: uuid.UUID,
    ) -> list[MailIntegration]:
        """List integrations, each annotated with its most recent import
        run (as a plain attribute, not a persisted relationship) so the
        frontend can show live/last-known progress on page load."""
        integrations = await self._repo.list_integrations_for_user(user_id)
        latest_runs = await self._repo.get_latest_runs_for_integrations(
            [i.id for i in integrations]
        )
        for integration in integrations:
            integration.latest_run = latest_runs.get(integration.id)
        return integrations

    async def get_import_run_status(
        self,
        run_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> IngestionImportRun:
        run = await self._repo.get_import_run(run_id)
        if not run:
            from app.core.exceptions import PlatformError

            raise PlatformError("Import run not found", status_code=404)

        # Verify ownership via the integration
        integration = await self._repo.get_integration_by_id(run.integration_id)
        if not integration or integration.user_id != requesting_user_id:
            from app.core.exceptions import PermissionDeniedException

            raise PermissionDeniedException()

        return run

    async def disconnect_integration(
        self,
        integration_id: uuid.UUID,
        requesting_user_id: uuid.UUID,
    ) -> None:
        """Mark an integration as disconnected and wipe stored tokens."""
        integration = await self._repo.get_integration_by_id(integration_id)
        if not integration:
            from app.core.exceptions import PlatformError

            raise PlatformError("Integration not found", status_code=404)

        if integration.user_id != requesting_user_id:
            from app.core.exceptions import PermissionDeniedException

            raise PermissionDeniedException()

        await self._repo.update_integration(
            integration_id,
            {
                "status": IntegrationStatus.DISCONNECTED.value,
                "encrypted_access_token": None,
                "encrypted_refresh_token": None,
                "token_expires_at": None,
            },
        )
        await self._db.commit()
        logger.info(
            "Integration %s disconnected by user %s", integration_id, requesting_user_id
        )
