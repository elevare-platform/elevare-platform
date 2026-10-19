"""Data access for first-login tour and checklist progress.

Every write is one upsert on the unique ``user_id``, so a double click, a retry or two
browser tabs cannot make a second row or record a step twice.
"""

import uuid

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding.models import UserOnboarding

_TABLE = UserOnboarding.__table__


class OnboardingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, user_id: uuid.UUID) -> UserOnboarding | None:
        found = await self._db.execute(
            select(UserOnboarding).where(UserOnboarding.user_id == user_id)
        )
        return found.scalar_one_or_none()

    async def finish_tour(self, user_id: uuid.UUID, outcome: str) -> None:
        """Record how the tour ended. The first outcome stays: closing a replay early
        must not turn "completed" into "skipped"."""
        statement = insert(UserOnboarding).values(
            id=uuid.uuid4(),
            user_id=user_id,
            tour_outcome=outcome,
            tour_finished_at=func.now(),
        )
        await self._db.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "tour_outcome": statement.excluded.tour_outcome,
                    "tour_finished_at": statement.excluded.tour_finished_at,
                    "updated_at": func.now(),
                },
                where=_TABLE.c.tour_outcome.is_(None),
            )
        )

    async def add_step(self, user_id: uuid.UUID, step: str) -> None:
        """Remember a checklist step as done. Safe to repeat: a step already in the
        list is left alone."""
        await self._db.execute(
            insert(UserOnboarding)
            .values(id=uuid.uuid4(), user_id=user_id, completed_steps=[step])
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "completed_steps": case(
                        (
                            _TABLE.c.completed_steps.contains([step]),
                            _TABLE.c.completed_steps,
                        ),
                        else_=func.array_append(_TABLE.c.completed_steps, step),
                    ),
                    "updated_at": func.now(),
                },
            )
        )

    async def dismiss_checklist(self, user_id: uuid.UUID) -> None:
        """Hide the checklist card. The first dismissal time stays."""
        statement = insert(UserOnboarding).values(
            id=uuid.uuid4(), user_id=user_id, checklist_dismissed_at=func.now()
        )
        await self._db.execute(
            statement.on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "checklist_dismissed_at": func.coalesce(
                        _TABLE.c.checklist_dismissed_at,
                        statement.excluded.checklist_dismissed_at,
                    ),
                    "updated_at": func.now(),
                },
            )
        )
