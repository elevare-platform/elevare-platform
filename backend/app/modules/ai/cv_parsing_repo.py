"""Data-access layer for CV parsing submissions."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import SubmissionNotFound
from app.core.pagination import paginate_cursor
from app.core.storage import StorageService
from app.modules.ai.enums import CVParsingStatus
from app.modules.ai.models import CVParsingCost, ParsedCVSubmission
from app.modules.users.models import User


class CVParsingRepo:
    """Repository for creating, updating, and querying ParsedCVSubmission records."""

    def __init__(
        self,
        db: AsyncSession,
        storage: StorageService,
    ) -> None:
        """Initialise with a database session and storage service."""
        self._db = db
        self._storage = storage

    async def submit_cv_for_parsing(
        self,
        filename: str,
        uploaded_by_id: uuid.UUID,
        cv_text_hash: str,
        parse_status: CVParsingStatus,
        parsed_data: dict | None = None,
        r2_key: str | None = None,
    ) -> ParsedCVSubmission:
        """Create a new ParsedCVSubmission record and return it."""
        submission = ParsedCVSubmission(
            uploaded_by=uploaded_by_id,
            filename=filename,
            cv_text_hash=cv_text_hash,
            parse_status=parse_status,
            parsed_data=parsed_data,
            r2_key=r2_key,
        )
        self._db.add(submission)
        await self._db.flush()
        await self._db.refresh(submission)
        return submission

    async def get_by_id(
        self,
        submission_id: uuid.UUID,
    ) -> ParsedCVSubmission | None:
        """Fetch a submission by its primary key with the uploader relationship loaded."""
        stmt = (
            select(ParsedCVSubmission)
            .options(selectinload(ParsedCVSubmission.uploader))
            .where(ParsedCVSubmission.id == submission_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        submission_id: uuid.UUID,
        data: dict,
    ) -> ParsedCVSubmission:
        """Apply a partial update dict to a submission and return the updated record."""
        submission = await self.get_by_id(submission_id)
        if not submission:
            raise SubmissionNotFound()

        for key, value in data.items():
            setattr(submission, key, value)

        self._db.add(submission)
        await self._db.flush()
        await self._db.refresh(submission)
        return submission

    async def list_submission(
        self,
        requesting_user: User,
        status: str | None = None,
        cursor: str | None = None,
        limit: int = 20,
    ) -> dict:
        """Return paginated submissions — employers see only their own."""
        from app.modules.users.enums import UserRole

        stmt = select(ParsedCVSubmission).options(
            selectinload(ParsedCVSubmission.uploader)
        )

        # Employers only see their own submissions
        if requesting_user.role == UserRole.EMPLOYER.value:
            stmt = stmt.where(ParsedCVSubmission.uploaded_by == requesting_user.id)

        if status:
            stmt = stmt.where(ParsedCVSubmission.parse_status == status)

        return await paginate_cursor(stmt, self._db, cursor=cursor, limit=limit)

    async def get_monthly_cost_summary(self):
        """Return aggregated total cost and call count for the current calendar month."""
        result = await self._db.execute(
            select(
                func.sum(CVParsingCost.cost_usd).label("total_cost"),
                func.count(CVParsingCost.id).label("total_calls"),
            ).where(
                func.date_trunc("month", CVParsingCost.created_at)
                == func.date_trunc("month", func.now())
            )
        )
        return result.one()
