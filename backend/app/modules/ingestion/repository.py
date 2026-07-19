"""Repository layer for the ingestion module.

Handles all DB reads and writes for MailIntegration and IngestionImportRun.
No business logic here — just persistence.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ingestion.enums import ImportStatus, IntegrationStatus, MailProvider
from app.modules.ingestion.models import IngestionImportRun, MailIntegration


class IngestionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------ #
    # MailIntegration
    # ------------------------------------------------------------------ #

    async def get_integration_by_id(
        self, integration_id: uuid.UUID
    ) -> MailIntegration | None:
        result = await self._db.execute(
            select(MailIntegration).where(MailIntegration.id == integration_id)
        )
        return result.scalar_one_or_none()

    async def get_integration_by_user_and_provider(
        self,
        user_id: uuid.UUID,
        provider: MailProvider,
    ) -> MailIntegration | None:
        result = await self._db.execute(
            select(MailIntegration).where(
                MailIntegration.user_id == user_id,
                MailIntegration.provider == provider.value,
            )
        )
        return result.scalar_one_or_none()

    async def list_integrations_for_user(
        self, user_id: uuid.UUID
    ) -> list[MailIntegration]:
        result = await self._db.execute(
            select(MailIntegration).where(MailIntegration.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create_integration(
        self,
        user_id: uuid.UUID,
        provider: MailProvider,
        encrypted_access_token: str,
        encrypted_refresh_token: str | None,
        token_expires_at: datetime | None,
        email_address: str,
    ) -> MailIntegration:
        integration = MailIntegration(
            user_id=user_id,
            provider=provider.value,
            status=IntegrationStatus.CONNECTED.value,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            token_expires_at=token_expires_at,
            email_address=email_address,
        )
        self._db.add(integration)
        await self._db.flush()
        return integration

    async def update_integration(
        self,
        integration_id: uuid.UUID,
        updates: dict,
    ) -> None:
        integration = await self.get_integration_by_id(integration_id)
        if not integration:
            return
        for key, value in updates.items():
            setattr(integration, key, value)
        await self._db.flush()

    async def get_integration_by_user_provider_and_email(
        self,
        user_id: uuid.UUID,
        provider: MailProvider,
        email_address: str,
    ) -> MailIntegration | None:
        result = await self._db.execute(
            select(MailIntegration).where(
                MailIntegration.user_id == user_id,
                MailIntegration.provider == provider.value,
                MailIntegration.email_address == email_address,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_integration(
        self,
        user_id: uuid.UUID,
        provider: MailProvider,
        encrypted_access_token: str,
        encrypted_refresh_token: str | None,
        token_expires_at: datetime | None,
        email_address: str,
    ) -> MailIntegration:
        """Create or update the integration for this user+provider+email combination.

        For Gmail, there's only ever one account so (user_id, provider) is unique.
        For Zoho, a user may have multiple accounts — we match on email_address too
        so each account gets its own row.
        """
        existing = await self.get_integration_by_user_provider_and_email(
            user_id, provider, email_address
        )
        if existing:
            existing.encrypted_access_token = encrypted_access_token
            if encrypted_refresh_token:
                existing.encrypted_refresh_token = encrypted_refresh_token
            existing.token_expires_at = token_expires_at
            existing.status = IntegrationStatus.CONNECTED.value
            existing.error_message = None
            await self._db.flush()
            return existing

        return await self.create_integration(
            user_id=user_id,
            provider=provider,
            encrypted_access_token=encrypted_access_token,
            encrypted_refresh_token=encrypted_refresh_token,
            token_expires_at=token_expires_at,
            email_address=email_address,
        )

    # ------------------------------------------------------------------ #
    # IngestionImportRun
    # ------------------------------------------------------------------ #

    async def create_import_run(
        self,
        integration_id: uuid.UUID,
        query_filter: str | None = None,
    ) -> IngestionImportRun:
        run = IngestionImportRun(
            integration_id=integration_id,
            status=ImportStatus.PENDING.value,
            query_filter=query_filter,
        )
        self._db.add(run)
        await self._db.flush()
        return run

    async def get_import_run(self, run_id: uuid.UUID) -> IngestionImportRun | None:
        result = await self._db.execute(
            select(IngestionImportRun).where(IngestionImportRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def get_latest_run_for_integration(
        self, integration_id: uuid.UUID
    ) -> IngestionImportRun | None:
        result = await self._db.execute(
            select(IngestionImportRun)
            .where(IngestionImportRun.integration_id == integration_id)
            .order_by(IngestionImportRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_runs_for_integrations(
        self, integration_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, IngestionImportRun]:
        """Return the most recent run per integration, in one query.

        Powers the integrations list showing live/last-known import
        progress without a browser tab having to stay open — DISTINCT ON
        is a single indexed query rather than N lookups per integration.
        """
        if not integration_ids:
            return {}
        result = await self._db.execute(
            select(IngestionImportRun)
            .where(IngestionImportRun.integration_id.in_(integration_ids))
            .distinct(IngestionImportRun.integration_id)
            .order_by(
                IngestionImportRun.integration_id,
                IngestionImportRun.created_at.desc(),
            )
        )
        runs = result.scalars().all()
        return {run.integration_id: run for run in runs}

    async def update_import_run(
        self,
        run_id: uuid.UUID,
        updates: dict,
    ) -> None:
        run = await self.get_import_run(run_id)
        if not run:
            return
        for key, value in updates.items():
            setattr(run, key, value)
        await self._db.flush()
