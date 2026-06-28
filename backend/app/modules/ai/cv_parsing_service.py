from app.modules.candidates.models import CandidateProfile
from app.modules.users.repository import UserRepository
from app.modules.candidates.repository import CandidateRepository
from app.modules.auth.repository import AuthRepository
from app.core.cv_pipeline.layer4_deterministic import DeterministicExtractionResult
from app.modules.users.enums import UserRole
from app.core.schemas import PaginationResponse
from app.core.pagination import paginate_cursor
from sqlalchemy import select
from app.core.exceptions import PermissionDeniedException
from app.modules.ai.cv_parsing_repo import CVParsingRepo
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.tasks import run_full_pipeline_task
from app.core.cv_pipeline.layer1_extraction import extract_text_from_pdf
from app.core.file_validation import validate_pdf_upload
from app.modules.users.models import User
from app.core.config import settings
from app.modules.ai.service import AIService
from app.core.storage import StorageService
import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import ParsedCVSubmission


logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days

class CVParsingService:
    def __init__(
        self,
        db: AsyncSession,
        storage: StorageService,
        redis: aioredis.Redis,
        ai_service: AIService,
        nlp,
    ) -> None:
        self._db = db
        self._storage = storage
        self._redis = redis
        self._ai_service = ai_service
        self._nlp = nlp
        self._repo = CVParsingRepo(db, storage)
        self._auth_repo = AuthRepository(db)
        self._user_repo = UserRepository(db)
        self._candidate_repo = CandidateRepository(db)
    
    def _compute_hash(self, text: str) -> str:
        """HMAC-SHA256 hash of CV text - used as a Redis cache key."""
        return hmac.new(
            settings.hmac_secret.encode(),
            text.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def submit_cv_for_parsing(
        self,
        uploaded_by: User,
        file: bytes,
        filename: str,
    ) -> ParsedCVSubmission:
        # Validate Pdf
        validate_pdf_upload(file, filename)

        # Layer 1 - Text extraction
        text_result = extract_text_from_pdf(file)

        # Compute HMAC hash for cache lookup
        cv_text_hash = self._compute_hash(text_result.text or "")

        # Check Redis cache
        cache_key = f"cv_parse:{cv_text_hash}"
        cached = await self._redis.get(cache_key)

        if cached:
            # Cache hit - create submission row with cached result, no pipeline needed.
            parsed_data = json.loads(cached)
            submission = await self._repo.submit_cv_for_parsing(
                filename,
                uploaded_by.id,
                cv_text_hash,
                CVParsingStatus.COMPLETED.value,
                parsed_data
            )
            await self._db.commit()
            logger.info("CV Parse cache hit", extra={"hash": cv_text_hash})
            return submission
        
        # Cache miss - upload to R2 and create pending submission
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        r2_key = f"cv-parsing/{uploaded_by.id}/{timestamp}_{filename}"
        await self._storage.upload_file(file, r2_key, "application/pdf")

        submission = await self._repo.submit_cv_for_parsing(
            filename,
            uploaded_by.id,
            cv_text_hash,
            parse_status=CVParsingStatus.PENDING.value,
            r2_key=r2_key
        )

        # Fire Celery task — only pass JSON-serialisable values
        run_full_pipeline_task.delay(
            submission_id=str(submission.id),
            cache_key=cache_key,
            file=file,
        )
        await self._db.commit()

        return submission
    
    async def get_submission(
        self,
        submission_id: uuid.UUID,
        requesting_user: User,
    ) -> ParsedCVSubmission:
        from app.core.exceptions import SubmissionNotFound, PermissionDeniedException
        from app.modules.users.enums import UserRole

        submission = await self._repo.get_by_id(submission_id)
        if not submission:
            raise SubmissionNotFound()

        # Employers can only see their own submissions
        if requesting_user.role == UserRole.EMPLOYER.value:
            if submission.uploaded_by != requesting_user.id:
                raise PermissionDeniedException()

        return submission
    
    async def list_submissions(
        self,
        requesting_user: User,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        from app.modules.ai.schema import SubmissionResponse

        result = await self._repo.list_submission(
            requesting_user, status, cursor, limit
        )
        result["items"] = [
            SubmissionResponse.from_submission(s) for s in result["items"]
        ]
        return result
    
    async def get_monthly_cost_summary(self) -> dict:
        now = datetime.now(UTC)
        row = await self._repo.get_monthly_cost_summary()
        return {
            "month": now.strftime("%Y-%m"),
            "total_cost_usd": float(row.total_cost or 0),
            "total_llm_calls": row.total_calls or 0,
        }

    async def generate_cv_url(self, submission_id: uuid.UUID, requesting_user: User) -> str:
        submission = await self._repo.get_by_id(submission_id)

        if submission.uploaded_by != requesting_user.id and requesting_user.role != UserRole.ADMIN.value:
            raise PermissionDeniedException()

        return await self._storage.generate_presigned_url(submission.r2_key, 60 * 15)
    
    async def create_candidate_from_submission(
        self,
        submission_id: uuid.UUID,
        requesting_user: User,
    ) -> CandidateProfile:
        from app.core.exceptions import SubmissionNotFound
        from app.modules.candidates.schema import EducationCreateSchema, WorkExperienceCreateSchema

        submission = await self._repo.get_by_id(submission_id)
        if not submission:
            raise SubmissionNotFound()

        parsed_data = submission.parsed_data or {}
        email = parsed_data.get("email")

        existing_user = None
        if email:
            existing_user = await self._user_repo.get_user_by_email(email)

        # If user exists, check for existing profile — never create a duplicate
        if existing_user:
            existing_profile = await self._candidate_repo.get_by_user_id(existing_user.id)
            if existing_profile:
                # Non-destructive merge — only fill fields that are currently empty
                updated = False
                if not existing_profile.skills and parsed_data.get("skills"):
                    existing_profile.skills = parsed_data["skills"]
                    updated = True
                if not existing_profile.years_of_experience and parsed_data.get("years_experience"):
                    existing_profile.years_of_experience = parsed_data["years_experience"]
                    updated = True
                if not existing_profile.linkedin_url and parsed_data.get("linkedin_url"):
                    existing_profile.linkedin_url = parsed_data["linkedin_url"]
                    updated = True

                if updated:
                    await self._db.flush()
                    await self._db.commit()

                return existing_profile

        # No existing profile — create one
        user_id = existing_user.id if existing_user else None
        profile = await self._candidate_repo.create(
            user_id=user_id,
            skills=parsed_data.get("skills"),
            years_of_experience=parsed_data.get("years_experience"),
            linkedin_url=parsed_data.get("linkedin_url"),
        )

        for entry in parsed_data.get("work_history", []):
            if entry.get("company") or entry.get("title"):
                await self._candidate_repo.add_work_experience(
                    profile.id,
                    WorkExperienceCreateSchema(
                        company_name=entry.get("company") or "",
                        job_title=entry.get("title") or "",
                        description=entry.get("description"),
                        is_current=entry.get("is_current", False),
                    ),
                )

        for entry in parsed_data.get("education", []):
            if entry.get("institution") or entry.get("degree"):
                await self._candidate_repo.add_education(
                    profile.id,
                    EducationCreateSchema(
                        institution_name=entry.get("institution") or "",
                        degree=entry.get("degree") or "",
                        field_of_study=entry.get("field") or "",
                    ),
                )

        await self._db.commit()
        return profile