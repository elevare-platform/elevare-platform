"""Business logic for the first-login tour and checklist."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.onboarding.models import CHECKLIST_STEPS, UserOnboarding
from app.modules.onboarding.repository import OnboardingRepository
from app.modules.onboarding.schemas import OnboardingResponse
from app.modules.users.models import User


def _present(row: UserOnboarding | None) -> OnboardingResponse:
    if row is None:
        return OnboardingResponse(
            tour_status="PENDING", completed_steps=[], checklist_dismissed=False
        )
    return OnboardingResponse(
        tour_status=row.tour_outcome or "PENDING",
        # Only steps that still exist, so retiring one later cannot break the response.
        completed_steps=[s for s in row.completed_steps if s in CHECKLIST_STEPS],
        checklist_dismissed=row.checklist_dismissed_at is not None,
    )


class OnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = OnboardingRepository(db)

    async def get(self, user: User) -> OnboardingResponse:
        return _present(await self._repo.get(user.id))

    async def finish_tour(self, user: User, outcome: str) -> OnboardingResponse:
        await self._repo.finish_tour(user.id, outcome)
        return await self._save_and_read(user)

    async def mark_step(self, user: User, step: str) -> OnboardingResponse:
        await self._repo.add_step(user.id, step)
        return await self._save_and_read(user)

    async def dismiss_checklist(self, user: User) -> OnboardingResponse:
        await self._repo.dismiss_checklist(user.id)
        return await self._save_and_read(user)

    async def _save_and_read(self, user: User) -> OnboardingResponse:
        await self._db.commit()
        return _present(await self._repo.get(user.id))
