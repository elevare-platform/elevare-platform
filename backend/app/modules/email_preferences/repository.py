"""Data access for addresses that have turned emails off."""

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.email_preferences.models import EmailSuppression


class EmailPreferenceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def is_suppressed(self, email: str) -> bool:
        found = await self._db.execute(
            select(EmailSuppression.id).where(EmailSuppression.email == email)
        )
        return found.scalar_one_or_none() is not None

    async def suppress(self, email: str, source: str) -> None:
        """Switch emails off for an address. Safe to repeat and to run twice at the
        same moment: the unique address makes the second one do nothing."""
        await self._db.execute(
            insert(EmailSuppression)
            .values(id=uuid.uuid4(), email=email, source=source)
            .on_conflict_do_nothing(index_elements=["email"])
        )

    async def unsuppress(self, email: str) -> None:
        """Switch emails back on for an address (nothing happens if they were on)."""
        await self._db.execute(
            delete(EmailSuppression).where(EmailSuppression.email == email)
        )
