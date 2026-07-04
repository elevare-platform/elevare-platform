import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import ParsedCVSubmission


class AIRepository:
    """Data-access layer for ParsedCVSubmission records."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session."""
        self._db = db

    async def get_submission_by_id(self, submission_id: uuid.UUID) -> ParsedCVSubmission | None:
        """Fetch a parsed CV submission by its primary key, or None if not found."""
        result = await self._db.execute(
            select(ParsedCVSubmission).where(ParsedCVSubmission.id == submission_id)
        )
        return result.scalar_one_or_none()
