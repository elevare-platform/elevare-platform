from app.modules.users.enums import UserRole
from app.modules.users.enums import AccountStatus
from app.modules.auth.service import AuthService
from app.modules.users.repository import UserRepository
from app.modules.ai.repository import AIRepository
from app.modules.talent_pool.schema import TalentPoolPromoteResponse
import uuid
import logging
from datetime import datetime, UTC


from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.talent_pool.schema import TalentPoolStatusUpdateRequest
from app.modules.talent_pool.schema import TalentPoolProfileResponse
from app.modules.talent_pool.enums import TalentPoolStatus
from app.modules.talent_pool.repository import TalentPoolRepository
from app.modules.users.models import User
from app.modules.talent_pool.schema import TalentPoolSubmitRequest
from app.core.exceptions import (
    JobNotFoundError,
    PermissionDeniedException,
    SubmissionNotFound,
    ValidationException
)
from app.modules.ai.cv_parsing_service import CVParsingService


logger = logging.getLogger(__name__)


class TalentPoolService:
    def __init__(self, db: AsyncSession, cv_service: CVParsingService):
        self._db = db
        self._cv_repo = cv_service
        self._repo = TalentPoolRepository(db)
        self._ai_repo = AIRepository(db)
        self._user_repo = UserRepository(db)
        self._auth_service = AuthService(db)
    
    async def submit(
        self,
        file: bytes,
        filename: str,
        data: TalentPoolSubmitRequest,
        current_user: User
    ):
        submission = await self._cv_repo.submit_cv_for_parsing(
            uploaded_by=current_user,
            file=file,
            filename=filename
        )
        
        # Create talent pool profile
        profile = await self._repo.create({
            "parsed_submission_id": submission.id,
            "source": data.source,
            "source_note": data.source_note,
            "sourced_for_job_id": data.sourced_for_job_id,
            "added_by": current_user.id,
            "status": TalentPoolStatus.NEW.value,
        })

        await self._db.commit()
        return TalentPoolProfileResponse.model_validate(profile)
    
    async def list_profiles(
        self,
        status: str | None,
        source: str | None,
        job_id: uuid.UUID | None,
        cursor: str | None,
        limit: int,
    ) -> dict:
        result = await self._repo.list(status, source, job_id, cursor, limit,)
        result['items'] = [TalentPoolProfileResponse.model_validate(t) for t in result["items"]]
        return result
    
    async def get_profile(self, id: uuid.UUID) -> TalentPoolProfileResponse:
        profile = await self._repo.get_by_id(id)
        if not profile:
            raise SubmissionNotFound()
        return TalentPoolProfileResponse.model_validate(profile)
    
    async def update_status(
        self,
        profile_id: uuid.UUID,
        data: TalentPoolStatusUpdateRequest
    ) -> TalentPoolProfileResponse:
        allowed_status = {s.value for s in TalentPoolStatus} - {TalentPoolStatus.PROMOTED.value, TalentPoolStatus.PROMOTED_PENDING.value}
        if data.status not in allowed_status:
            raise ValidationException(f"Invalid status. Allowed: {allowed_status}")

        profile = await self._repo.update(profile_id, {"status": data.status})
        if not profile:
            raise SubmissionNotFound()
        await self._db.commit()
        return TalentPoolProfileResponse.model_validate(profile)
    
    async def promote(
        self,
        profile_id: uuid.UUID,
        current_user
    ) -> TalentPoolPromoteResponse:
        profile = await self._repo.get_by_id(profile_id)
        if not profile:
            raise SubmissionNotFound()
        
        # Load Parsed data to get email
        submission = await self._ai_repo.get_submission_by_id(profile.parsed_submission_id)
        if not submission or not submission.parsed_data:
            raise ValidationException("Parsed data not available.")
        
        email = (submission.parsed_data or {}).get("email")
        if not email:
            raise ValidationException("Parsed CV has no email address — cannot send invite")
        
        existing_user = await self._user_repo.get_user_by_email(email)
        if existing_user and existing_user.account_status == AccountStatus.ACTIVE.value:
            return TalentPoolPromoteResponse(
                message="A user with this email already exists and is active. Manual review required.",
                status="conflict",
                conflict_email=email,
            )
        
        # Trigger invite via existing auth flow
        raw_token = await self._auth_service.create_invite(
            email,
            role=UserRole.CANDIDATE.value,
            admin_id=current_user.id
        )

        if hasattr(self._db, '_app') or True:  # always log in stub mode check
            logger.info("Talent pool promote invite sent to %s (token logged in stub mode)", email)

        await self._repo.update(profile_id, {
            "status": TalentPoolStatus.PROMOTED_PENDING.value,
            "last_invite_sent_at": datetime.now(UTC),
        })
        await self._db.commit()

        return TalentPoolPromoteResponse(
            message="Invite sent. Profile will be promoted once candidate confirms.",
            status="invite_sent",
        )
        
        
