"""Remembering which CVs someone has opened (docs/08_DECISIONS.md, item 35).

"Seen" means OPENED: the employer opened a talent pool CV or its details, or an applicant's CV,
profile or cover letter; the reader of a shared link opened a candidate's details or CV. Scrolling
past a name does not count. Plain functions over a few small tables (``seen/models.py``); every
write is an INSERT that ignores a repeat, so a double click or two tabs never raise an error and
never create a second row.

Every call is safe on a database whose migration has not run yet (see ``core/schema_guard.py``):
the new containers start before ``alembic upgrade head``, and a missing table must cost only the
markers, never the page they decorate.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schema_guard import tolerate_missing
from app.modules.seen.models import (
    ApplicationView,
    EmployerSeenBaseline,
    SharedLinkItemView,
    SharedLinkVisit,
    TalentPoolProfileView,
)

# Two opens of a shared link this close together are one visit: a reload, or the reader
# switching tabs and back, must not turn "new since your last visit" into nothing.
SAME_VISIT_WITHIN = timedelta(minutes=30)
# A shared link remembers at most this many opened candidates (a list is at most a few hundred),
# so a reader cannot grow the table by sending keys.
MAX_OPENED_PER_LINK = 1000


def item_key(token_id: uuid.UUID, source: str, record_id: uuid.UUID) -> str:
    """The opaque name a shared link gives one candidate: the same every time for that link,
    different on every other link, and not the candidate's own id."""
    digest = hashlib.sha256(f"{token_id}:{source}:{record_id}".encode()).hexdigest()
    return digest[:16]


def valid_item_key(value: str) -> bool:
    return len(value) == 16 and all(char in "0123456789abcdef" for char in value)


class SeenService:
    """The seen/new state for employers (talent pool, applicants) and for shared links."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # -- the employer's own markers -----------------------------------------------------------

    async def baseline(self, employer_id: uuid.UUID, now: datetime | None = None) -> datetime | None:
        """When this employer first used the markers (made now, the first time). A CV added before
        it is never new to them. None when the markers cannot be kept yet (the tables are not
        there): nothing is then shown as new."""
        now = now or datetime.now(UTC)

        async def operation() -> datetime:
            await self._db.execute(
                insert(EmployerSeenBaseline)
                .values(id=uuid.uuid4(), employer_id=employer_id, baseline_at=now)
                .on_conflict_do_nothing(index_elements=["employer_id"])
            )
            result = await self._db.execute(
                select(EmployerSeenBaseline.baseline_at).where(EmployerSeenBaseline.employer_id == employer_id)
            )
            return result.scalar_one()

        return await tolerate_missing(self._db, operation, None)

    async def opened_profile_ids(self, employer_id: uuid.UUID, profile_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        if not profile_ids:
            return set()

        async def operation() -> set[uuid.UUID]:
            result = await self._db.execute(
                select(TalentPoolProfileView.talent_pool_profile_id).where(
                    TalentPoolProfileView.employer_id == employer_id,
                    TalentPoolProfileView.talent_pool_profile_id.in_(profile_ids),
                )
            )
            return set(result.scalars().all())

        return await tolerate_missing(self._db, operation, set())

    async def mark_profile_opened(
        self, employer_id: uuid.UUID, profile_id: uuid.UUID, now: datetime | None = None
    ) -> None:
        async def operation() -> None:
            await self._db.execute(
                insert(TalentPoolProfileView)
                .values(
                    id=uuid.uuid4(),
                    employer_id=employer_id,
                    talent_pool_profile_id=profile_id,
                    viewed_at=now or datetime.now(UTC),
                )
                .on_conflict_do_nothing(constraint="uq_talent_pool_profile_view")
            )

        await tolerate_missing(self._db, operation, None)

    async def opened_application_ids(self, employer_id: uuid.UUID, application_ids: list[uuid.UUID]) -> set[uuid.UUID]:
        """Which of these applications the employer has opened."""
        if not application_ids:
            return set()

        async def operation() -> set[uuid.UUID]:
            result = await self._db.execute(
                select(ApplicationView.application_id).where(
                    ApplicationView.employer_id == employer_id,
                    ApplicationView.application_id.in_(application_ids),
                )
            )
            return set(result.scalars().all())

        return await tolerate_missing(self._db, operation, set())

    async def mark_application_opened(
        self, employer_id: uuid.UUID, application_id: uuid.UUID, now: datetime | None = None
    ) -> None:
        async def operation() -> None:
            await self._db.execute(
                insert(ApplicationView)
                .values(
                    id=uuid.uuid4(),
                    employer_id=employer_id,
                    application_id=application_id,
                    viewed_at=now or datetime.now(UTC),
                )
                .on_conflict_do_nothing(constraint="uq_application_view")
            )

        await tolerate_missing(self._db, operation, None)

    # -- a shared link ------------------------------------------------------------------------

    async def record_visit(self, token_id: uuid.UUID, now: datetime | None = None) -> datetime | None:
        """Note that the link was opened now, and return when the reader was here BEFORE this
        visit (None the first time). A second open within ``SAME_VISIT_WITHIN`` is the same
        visit and returns the same earlier time."""
        now = now or datetime.now(UTC)

        async def operation() -> datetime | None:
            result = await self._db.execute(select(SharedLinkVisit).where(SharedLinkVisit.token_id == token_id))
            visit = result.scalar_one_or_none()
            if visit is None:
                await self._db.execute(
                    insert(SharedLinkVisit)
                    .values(id=uuid.uuid4(), token_id=token_id, previous_visit_at=None, last_visit_at=now)
                    .on_conflict_do_nothing(index_elements=["token_id"])
                )
                return None
            if now - visit.last_visit_at >= SAME_VISIT_WITHIN:
                visit.previous_visit_at = visit.last_visit_at
            visit.last_visit_at = now
            return visit.previous_visit_at

        return await tolerate_missing(self._db, operation, None)

    async def opened_keys(self, token_id: uuid.UUID) -> set[str]:
        async def operation() -> set[str]:
            result = await self._db.execute(
                select(SharedLinkItemView.item_key).where(SharedLinkItemView.token_id == token_id)
            )
            return set(result.scalars().all())

        return await tolerate_missing(self._db, operation, set())

    async def mark_item_opened(self, token_id: uuid.UUID, key: str, now: datetime | None = None) -> bool:
        """Remember that the reader of this link opened the candidate named ``key``. False when
        the key is not a key or the link has reached its limit."""
        if not valid_item_key(key):
            return False

        async def operation() -> bool:
            count = (
                await self._db.execute(
                    select(func.count()).select_from(SharedLinkItemView).where(SharedLinkItemView.token_id == token_id)
                )
            ).scalar_one()
            if count >= MAX_OPENED_PER_LINK:
                return False
            await self._db.execute(
                insert(SharedLinkItemView)
                .values(id=uuid.uuid4(), token_id=token_id, item_key=key, viewed_at=now or datetime.now(UTC))
                .on_conflict_do_nothing(constraint="uq_shared_link_item_view")
            )
            return True

        return await tolerate_missing(self._db, operation, False)
