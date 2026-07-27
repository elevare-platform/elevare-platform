"""HTTP endpoints for saved candidates."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_role
from app.core.schemas import SuccessResponse
from app.modules.saved_candidates.schemas import (
    SaveCandidateRequest,
    SavedCandidateIdsResponse,
    SavedCandidateListResponse,
)
from app.modules.saved_candidates.service import SavedCandidateService
from app.modules.users.models import User

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> SavedCandidateService:
    return SavedCandidateService(db)


@router.get("", response_model=SavedCandidateListResponse, status_code=200)
async def list_saved_candidates(
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: SavedCandidateService = Depends(get_service),
):
    """Return the authenticated employer's full saved-candidates list."""
    return await service.list_for_employer(current_user.id)


@router.get("/ids", response_model=SavedCandidateIdsResponse, status_code=200)
async def list_saved_candidate_ids(
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: SavedCandidateService = Depends(get_service),
):
    """Return just the saved profile ids — cheap check for heart state on result cards.

    Must be declared before /{talent_pool_profile_id}-style routes if any
    are added later, to avoid a route conflict.
    """
    return await service.list_ids(current_user.id)


@router.post("", response_model=SuccessResponse, status_code=201)
async def save_candidate(
    body: SaveCandidateRequest,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: SavedCandidateService = Depends(get_service),
):
    """Save a candidate to the employer's saved list (idempotent).

    Accepts either ``talent_pool_profile_id`` (search, AI matches) or
    ``candidate_profile_id`` (the applicants list, which doesn't carry the
    former directly) — the service resolves whichever is given.
    """
    await service.save(
        current_user.id,
        body.talent_pool_profile_id,
        body.candidate_profile_id,
        body.note,
    )
    return SuccessResponse(message="Candidate saved")


@router.delete("", response_model=SuccessResponse, status_code=200)
async def unsave_candidate(
    talent_pool_profile_id: uuid.UUID | None = Query(default=None),
    candidate_profile_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: SavedCandidateService = Depends(get_service),
):
    """Remove a candidate from the employer's saved list.

    Query params rather than a path segment, so either id type works —
    same reasoning as save_candidate above.
    """
    await service.unsave(current_user.id, talent_pool_profile_id, candidate_profile_id)
    return SuccessResponse(message="Candidate removed from saved list")
