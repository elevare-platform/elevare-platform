"""Data-access layer for employer-specific queries."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.employer.models import KYCDocument
from app.modules.jobs.models import Job
from app.modules.users.models import EmployerProfile

from .schemas import EmployerStats


class EmployerRepository:
    """Handles database queries scoped to a specific employer."""

    def __init__(self, db: AsyncSession):
        """Initialise with an async database session."""
        self._db = db

    async def get_stats(self, employer_id) -> EmployerStats:
        """Return aggregated job counts for the given employer."""
        stmt = select(
            func.count(Job.id).label("total"),
            func.count(Job.id).filter(Job.status == "ACTIVE").label("active"),
            func.count(Job.id).filter(Job.status == "DRAFT").label("draft"),
            func.count(Job.id).filter(Job.status == "CLOSED").label("closed"),
        ).where(Job.employer_id == employer_id)

        result = await self._db.execute(stmt)
        row = result.mappings().one_or_none()

        if not row:
            return EmployerStats(total_jobs=0, active_jobs=0, draft_jobs=0, closed_jobs=0)

        return EmployerStats(
            total_jobs=row["total"],
            active_jobs=row["active"],
            draft_jobs=row["draft"],
            closed_jobs=row["closed"],
            total_applications=0,
        )

    # ------------------------------------------------------------------
    # KYC
    # ------------------------------------------------------------------

    async def get_employer_profile_by_user_id(
        self, user_id: uuid.UUID
    ) -> EmployerProfile | None:
        """Return the employer profile with kyc_documents eagerly loaded."""
        stmt = (
            select(EmployerProfile)
            .where(EmployerProfile.user_id == user_id)
            .options(selectinload(EmployerProfile.kyc_documents))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_kyc_document(
        self,
        employer_profile_id: uuid.UUID,
        key: str,
        filename: str,
        document_type: str,
    ) -> KYCDocument:
        """Persist a KYC document record and return it."""
        doc = KYCDocument(
            employer_profile_id=employer_profile_id,
            key=key,
            filename=filename,
            document_type=document_type,
        )
        self._db.add(doc)
        await self._db.flush()
        return doc

    async def get_kyc_document(
        self, document_id: uuid.UUID
    ) -> KYCDocument | None:
        """Return a KYC document by its primary key."""
        return await self._db.get(KYCDocument, document_id)

    async def delete_kyc_document(self, doc: KYCDocument) -> None:
        """Delete a KYC document record."""
        await self._db.delete(doc)

    async def set_kyc_status(
        self,
        profile: EmployerProfile,
        status: str,
        rejection_reason: str | None = None,
    ) -> EmployerProfile:
        """Update kyc_status and related timestamps on the employer profile."""
        from app.modules.employer.enums import KYCStatus

        profile.kyc_status = status
        if status == KYCStatus.PENDING.value:
            profile.kyc_submitted_at = datetime.now(UTC)
        elif status in (KYCStatus.APPROVED.value, KYCStatus.REJECTED.value):
            profile.kyc_reviewed_at = datetime.now(UTC)
            profile.kyc_rejection_reason = rejection_reason
        await self._db.flush()
        return profile
