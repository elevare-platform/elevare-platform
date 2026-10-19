"""Request and response shapes for the first-login tour and checklist endpoints."""

from typing import Literal

from pydantic import BaseModel

TourStatus = Literal["PENDING", "COMPLETED", "SKIPPED"]
TourOutcome = Literal["COMPLETED", "SKIPPED"]
ChecklistStep = Literal[
    "talent_pool", "candidate_search", "cv_parser", "interview_list", "credits"
]


class OnboardingResponse(BaseModel):
    """``PENDING`` means the user has not seen the tour yet. ``completed_steps`` are only
    the steps the app reports; profile, verification and first job come from the data
    the dashboard already loads."""

    tour_status: TourStatus
    completed_steps: list[ChecklistStep]
    checklist_dismissed: bool


class TourFinished(BaseModel):
    outcome: TourOutcome


class StepDone(BaseModel):
    step: ChecklistStep
