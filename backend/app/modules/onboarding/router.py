"""Endpoints for the first-login tour and the "Get started" checklist.

Each person has their own progress, even inside one company.

Employers and candidates (each has a tour):
  GET  /me                    where the user is (never creates anything)
  POST /me/tour               the tour was completed or skipped

Employers only (the candidate dashboard has no checklist card):
  POST /me/steps              a checklist step was done (safe to repeat)
  POST /me/checklist/dismiss  hide the checklist card
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.limiter import limiter
from app.modules.onboarding.schemas import OnboardingResponse, StepDone, TourFinished
from app.modules.onboarding.service import OnboardingService
from app.modules.users.models import User

router = APIRouter()

EmployerUser = Depends(require_role("EMPLOYER"))
TourUser = Depends(require_role("EMPLOYER", "CANDIDATE"))


@router.get("/me", response_model=OnboardingResponse)
async def get_my_onboarding(
    db: AsyncSession = Depends(get_db),
    current_user: User = TourUser,
):
    return await OnboardingService(db).get(current_user)


@router.post("/me/tour", response_model=OnboardingResponse)
@limiter.limit("30/minute")
async def finish_tour(
    request: Request,
    data: TourFinished,
    db: AsyncSession = Depends(get_db),
    current_user: User = TourUser,
):
    return await OnboardingService(db).finish_tour(current_user, data.outcome)


@router.post("/me/steps", response_model=OnboardingResponse)
@limiter.limit("60/minute")
async def mark_step(
    request: Request,
    data: StepDone,
    db: AsyncSession = Depends(get_db),
    current_user: User = EmployerUser,
):
    return await OnboardingService(db).mark_step(current_user, data.step)


@router.post("/me/checklist/dismiss", response_model=OnboardingResponse)
@limiter.limit("30/minute")
async def dismiss_checklist(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = EmployerUser,
):
    return await OnboardingService(db).dismiss_checklist(current_user)
