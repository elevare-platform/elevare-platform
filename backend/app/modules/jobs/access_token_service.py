from datetime import datetime, timedelta, UTC
import logging
import secrets
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import JobNotFoundError, PermissionDeniedException, TokenNotFoundError
from app.modules.applications.schema import ApplicationFilters
from app.modules.applications.repository import ApplicationRepository
from app.modules.users.models import User
from app.modules.users.enums import UserRole
from app.modules.jobs.access_token_schema import (
    AccessTokenResponse,
    CreateAccessTokenRequest,
    PublicApplicantsItem,
    PublicApplicantsResponse,
)
from app.modules.jobs.access_token_repository import AccessTokenRepository
from app.modules.jobs.repository import JobRepository

logger = logging.getLogger(__name__)


class AccessTokenService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._repo = AccessTokenRepository(db)
        self._job_repo = JobRepository(db)
        self._app_repo = ApplicationRepository(db)
    
    async def create_access_token(
        self, job_id: uuid.UUID,
        data: CreateAccessTokenRequest,
        current_user: User
    ) -> AccessTokenResponse:
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        
        # Only the job's employer or an admin can generate a token
        if current_user.role != UserRole.ADMIN.value and current_user.id != job.employer_id:
            raise PermissionDeniedException("You do not own this job")
        
        token = await self._repo.create(
            {
                "token": secrets.token_urlsafe(32),
                "job_id": job_id,
                "created_by_id": current_user.id,
                "disclose_names": data.disclose_names,
                "expires_at": datetime.now(UTC) + timedelta(days=data.expires_in_days),
            }
        )

        await self._db.commit()
        return AccessTokenResponse.model_validate(
            token
        )
    
    async def get_all_access_tokens(
        self,
        job_id: uuid.UUID,
        current_user: User
    ) -> list[AccessTokenResponse]:
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()

        # Only the job's employer or an admin can view tokens
        if current_user.role != UserRole.ADMIN.value and current_user.id != job.employer_id:
            raise PermissionDeniedException("You do not own this job")

        tokens = await self._repo.get_all_by_job(job_id)
        return [AccessTokenResponse.model_validate(token) for token in tokens]
    
    async def delete_access_token(
        self,
        job_id: uuid.UUID,
        token_id: uuid.UUID,
        current_user: User
    ):
        job = await self._job_repo.get_by_id(job_id)
        if not job:
            raise JobNotFoundError()
        
        # Only the job's employer or an admin can delete a token
        if current_user.role != UserRole.ADMIN.value and current_user.id != job.employer_id:
            raise PermissionDeniedException("You do not own this job")
        
        token = await self._repo.get_by_id(token_id)
        if not token:
            raise TokenNotFoundError()
        
        await self._repo.delete(token)
    
    async def revoke_token(
        self,
        token_id: uuid.UUID,
        current_user: User
    ) -> AccessTokenResponse:
        token = await self._repo.get_by_id(token_id)
        if not token:
            raise TokenNotFoundError()
        
        job = await self._job_repo.get_by_id(token.job_id)

        if current_user.role != UserRole.ADMIN.value and job.employer_id != current_user.id:
            raise PermissionDeniedException("You do not own this job")

        token = await self._repo.revoke(token_id, current_user.id)
        await self._db.commit()
        return AccessTokenResponse.model_validate(token)
    
    async def get_public_applicants(
        self,
        token_str: str
    ) -> PublicApplicantsResponse:
        token = await self._repo.get_valid_by_token(token_str)
        
        # Return 404 for invalid, expired, or revoked tokens - never confirm existence
        if not token:
            raise JobNotFoundError()
        
        job = await self._job_repo.get_by_id(token.job_id)

        # Load applicants sorted by ai_score desc
        paginated = await self._app_repo.get_job_applicants(
            job_id=token.job_id,
            filters=ApplicationFilters(sort="ai_score"),
            limit=200,
            cursor=None
        )

        applicants = []
        for application in paginated["items"]:
            candidate = application.candidate
            candidate_profile = getattr(candidate, "candidate_profile", None)

            # Build initials from first + last name
            first = candidate.first_name or ""
            last = candidate.last_name or ""
            initials = f"{first[:1]}{last[:1]}".upper()


            # Name only disclosed if token allows it AND candidate consented
            full_name = None
            if (
                token.disclose_names
                and candidate_profile
                and candidate_profile.cv_sharing_consent
            ):
                full_name = f"{first} {last}".strip()
            

            # CV snippet from parsed_data.summary - never full CV text
            cv_snippet = None
            cv = getattr(application, "cv", None)
            if cv and hasattr(cv, "submission") and cv.submission:
                summary = (cv.submission.parsed_data or {}).get("summary") or ""
                cv_snippet = summary[:200] + "..." if len(summary) > 200 else summary
            
            applicants.append(PublicApplicantsItem(
                initials=initials,
                full_name=full_name,
                ai_score=application.ai_score,
                ai_fit_summary=application.ai_fit_summary,
                ai_strengths=application.ai_strengths,
                ai_weaknesses=application.ai_weaknesses,
                cv_snippet=cv_snippet,
            ))
        
        return PublicApplicantsResponse(
            job_title=job.title,
            expires_at=token.expires_at,
            applicants=applicants,
        )

