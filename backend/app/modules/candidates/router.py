"""HTTP endpoints for candidate profiles, CVs, and documents."""

import uuid

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_redis_client, require_role
from app.core.schemas import SuccessResponse
from app.core.storage import StorageService, get_storage_service
from app.modules.candidates.schema import (
    CandidateCvsResponse,
    CandidateDocumentsResponse,
    CertificationCreateSchema,
    CertificationResponse,
    EducationCreateSchema,
    EducationResponse,
    ProfileResponse,
    UpdateProfileSchema,
    WorkExperienceCreateSchema,
    WorkExperienceResponse,
)
from app.modules.candidates.service import CandidateService
from app.modules.users.models import User

router = APIRouter()


def get_service(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
    redis: aioredis.Redis = Depends(get_redis_client),
) -> CandidateService:
    """Construct a :class:`CandidateService` with injected DB session, storage, and Redis."""
    return CandidateService(db, storage, redis)


# ------------------------------------------------------------------
# Candidate — own profile
# ------------------------------------------------------------------


@router.get("/me", response_model=ProfileResponse, status_code=200)
async def get_my_profile(
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Return the authenticated candidate's own profile."""
    return await service.get_my_profile(current_user.id)


@router.put("/me", response_model=ProfileResponse, status_code=200)
async def update_my_profile(
    data: UpdateProfileSchema,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Update the authenticated candidate's own profile."""
    return await service.update_my_profile(current_user.id, data)


@router.get("/me/introductions", status_code=200)
async def get_my_introductions(
    current_user: User = Depends(require_role("CANDIDATE")),
    db: AsyncSession = Depends(get_db),
):
    """Return every introduction request made about the authenticated candidate.

    Lets a self-registered candidate see requests in-app instead of only
    via email — see docs/talent-pool-isolation-and-introduction-routing.md.
    """
    from app.core.exceptions import ProfileNotFoundException
    from app.modules.candidates.repository import CandidateRepository
    from app.modules.introductions.service import IntroductionService

    candidate_repo = CandidateRepository(db)
    profile = await candidate_repo.get_by_user_id(current_user.id)
    if profile is None:
        raise ProfileNotFoundException()

    intro_service = IntroductionService(db)
    return await intro_service.list_for_candidate(profile.id)


# ------------------------------------------------------------------
# Candidate — CVs
# ------------------------------------------------------------------


@router.post("/me/cv", response_model=CandidateCvsResponse, status_code=201)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Upload a new CV for the authenticated candidate."""
    contents = await file.read()
    return await service.upload_cv(current_user.id, contents, file.filename)


@router.get("/me/cvs", response_model=list[CandidateCvsResponse], status_code=200)
async def get_my_cvs(
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Return all CVs belonging to the authenticated candidate."""
    return await service.get_cvs(current_user.id)


@router.get("/me/cv/{cv_id}/url", response_model=SuccessResponse, status_code=200)
async def get_cv_url(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Generate a presigned download URL for one of the candidate's own CVs."""
    url = await service.generate_cv_url(cv_id, current_user.id)
    return SuccessResponse(message="CV URL generated", data={"url": url})


@router.put("/me/cv/{cv_id}/default", response_model=SuccessResponse, status_code=200)
async def set_cv_default(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Set a specific CV as the candidate's default."""
    await service.set_cv_default(cv_id, current_user.id)
    return SuccessResponse(message="CV set as default")


@router.delete("/me/cv/{cv_id}", response_model=SuccessResponse, status_code=200)
async def delete_cv(
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Delete one of the authenticated candidate's CVs."""
    await service.delete_cv(cv_id, current_user.id)
    return SuccessResponse(message="CV deleted successfully")


# ------------------------------------------------------------------
# Candidate — documents
# ------------------------------------------------------------------


@router.post(
    "/me/documents", response_model=CandidateDocumentsResponse, status_code=201
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Upload a supporting document for the authenticated candidate."""
    contents = await file.read()
    return await service.upload_document(current_user.id, contents, file.filename)


@router.get(
    "/me/documents", response_model=list[CandidateDocumentsResponse], status_code=200
)
async def get_my_documents(
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Return all supporting documents for the authenticated candidate."""
    return await service.get_my_documents(current_user.id)


@router.get(
    "/me/documents/{document_id}/url", response_model=SuccessResponse, status_code=200
)
async def get_document_url(
    document_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Generate a presigned download URL for one of the candidate's own documents."""
    url = await service.generate_document_url(document_id, current_user.id)
    return SuccessResponse(message="Document URL generated", data={"url": url})


@router.delete(
    "/me/documents/{document_id}", response_model=SuccessResponse, status_code=200
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Delete one of the authenticated candidate's supporting documents."""
    await service.delete_document(document_id, current_user.id)
    return SuccessResponse(message="Document deleted successfully")


# ------------------------------------------------------------------
# Candidate — work experience
# ------------------------------------------------------------------


@router.post(
    "/me/work-experience", response_model=WorkExperienceResponse, status_code=201
)
async def add_work_experience(
    data: WorkExperienceCreateSchema,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Add a work experience entry to the authenticated candidate's profile."""
    return await service.add_work_experience(current_user.id, data)


@router.delete(
    "/me/work-experience/{entry_id}", response_model=SuccessResponse, status_code=200
)
async def delete_work_experience(
    entry_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Delete a work experience entry."""
    await service.delete_work_experience(entry_id, current_user.id)
    return SuccessResponse(message="Work experience deleted")


# ------------------------------------------------------------------
# Candidate — education
# ------------------------------------------------------------------


@router.post("/me/education", response_model=EducationResponse, status_code=201)
async def add_education(
    data: EducationCreateSchema,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Add an education entry to the authenticated candidate's profile."""
    return await service.add_education(current_user.id, data)


@router.delete(
    "/me/education/{entry_id}", response_model=SuccessResponse, status_code=200
)
async def delete_education(
    entry_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Delete an education entry."""
    await service.delete_education(entry_id, current_user.id)
    return SuccessResponse(message="Education entry deleted")


# ------------------------------------------------------------------
# Candidate — certifications
# ------------------------------------------------------------------


@router.post(
    "/me/certifications", response_model=CertificationResponse, status_code=201
)
async def add_certification(
    data: CertificationCreateSchema,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Add a certification to the authenticated candidate's profile."""
    return await service.add_certification(current_user.id, data)


@router.delete(
    "/me/certifications/{entry_id}", response_model=SuccessResponse, status_code=200
)
async def delete_certification(
    entry_id: uuid.UUID,
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Delete a certification entry."""
    await service.delete_certification(entry_id, current_user.id)
    return SuccessResponse(message="Certification deleted")


# ------------------------------------------------------------------
# Candidate — profile views (must be before /{candidate_profile_id})
# ------------------------------------------------------------------


@router.get("/me/profile-views", status_code=200)
async def profile_view_history(
    current_user: User = Depends(require_role("CANDIDATE")),
    service: CandidateService = Depends(get_service),
    cursor: str | None = None,
    limit: int = 20,
):
    """Return the profile view history for the authenticated candidate."""
    return await service.get_profile_views(current_user.id, cursor, limit)


# ------------------------------------------------------------------
# Employer / Admin — view candidate profiles
# ------------------------------------------------------------------


@router.get("/{candidate_profile_id}", response_model=ProfileResponse, status_code=200)
async def get_candidate_profile(
    candidate_profile_id: uuid.UUID,
    job_id: uuid.UUID | None = None,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN", "CANDIDATE")),
    service: CandidateService = Depends(get_service),
):
    """Return a candidate profile by ID (employer/admin access)."""
    return await service.get_profile_by_id(candidate_profile_id, current_user, job_id)


@router.get(
    "/{candidate_profile_id}/cv/{cv_id}/url",
    response_model=SuccessResponse,
    status_code=200,
)
async def get_candidate_cv_url(
    candidate_profile_id: uuid.UUID,
    cv_id: uuid.UUID,
    current_user: User = Depends(require_role("EMPLOYER", "ADMIN")),
    service: CandidateService = Depends(get_service),
):
    """Employer/admin gets a presigned URL for a candidate's CV."""
    # Verify the profile exists and the requester has access
    profile = await service.get_profile_by_id(candidate_profile_id, current_user)
    cv = await service._repo.get_cv(cv_id)
    if cv is None or cv.candidate_id != profile.id:
        from app.core.exceptions import DocumentNotFoundError

        raise DocumentNotFoundError()
    url = await service._storage.generate_presigned_url(cv.key, 60 * 15)
    return SuccessResponse(message="CV URL generated", data={"url": url})


# ------------------------------------------------------------------
# Employer / Admin — view candidate profiles
# ------------------------------------------------------------------


@router.get("", response_model=list[ProfileResponse], status_code=200)
async def list_all_candidates(
    current_user: User = Depends(require_role("ADMIN")),
    service: CandidateService = Depends(get_service),
):
    """Return all candidate profiles (admin only)."""
    return await service.list_all_profiles()
