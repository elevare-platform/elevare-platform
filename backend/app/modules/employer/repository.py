"""Data-access layer for employer-specific queries."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.employer.models import KYCDocument
from app.modules.jobs.models import Job
from app.modules.users.models import Organization, User

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
        ).where(
            Job.employer_id == employer_id,
            Job.is_general_interest.is_(False),
        )

        result = await self._db.execute(stmt)
        row = result.mappings().one_or_none()

        if not row:
            return EmployerStats(
                total_jobs=0, active_jobs=0, draft_jobs=0, closed_jobs=0
            )

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

    async def get_organization_by_user_id(
        self, user_id: uuid.UUID
    ) -> Organization | None:
        """Return the organization the given user belongs to, kyc_documents eagerly loaded.

        Joins through ``User.organization_id`` rather than looking the
        organization up by a 1:1 owner FK — a user's organization may be
        shared with teammates, not owned exclusively by them.
        """
        stmt = (
            select(Organization)
            .join(User, User.organization_id == Organization.id)
            .where(User.id == user_id)
            .options(selectinload(Organization.kyc_documents))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_organization_by_id(
        self, organization_id: uuid.UUID
    ) -> Organization | None:
        """Return the organization the given organization_id.
        If the user does not belong to an organization, return None.

        """
        stmt = select(Organization).where(Organization.id == organization_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_kyc_document(
        self,
        organization_id: uuid.UUID,
        key: str,
        filename: str,
        document_type: str,
    ) -> KYCDocument:
        """Persist a KYC document record and return it."""
        doc = KYCDocument(
            organization_id=organization_id,
            key=key,
            filename=filename,
            document_type=document_type,
        )
        self._db.add(doc)
        await self._db.flush()
        return doc

    async def get_kyc_document(self, document_id: uuid.UUID) -> KYCDocument | None:
        """Return a KYC document by its primary key."""
        return await self._db.get(KYCDocument, document_id)

    async def delete_kyc_document(self, doc: KYCDocument) -> None:
        """Delete a KYC document record."""
        await self._db.delete(doc)

    async def set_kyc_status(
        self,
        organization: Organization,
        status: str,
        rejection_reason: str | None = None,
    ) -> Organization:
        """Update kyc_status and related timestamps on the organization."""
        from app.modules.employer.enums import KYCStatus

        organization.kyc_status = status
        if status == KYCStatus.PENDING.value:
            organization.kyc_submitted_at = datetime.now(UTC)
        elif status in (KYCStatus.APPROVED.value, KYCStatus.REJECTED.value):
            organization.kyc_reviewed_at = datetime.now(UTC)
            organization.kyc_rejection_reason = rejection_reason
        await self._db.flush()
        return organization

    # ------------------------------------------------------------------
    # Team membership
    # ------------------------------------------------------------------

    async def list_members(self, organization_id: uuid.UUID) -> list[User]:
        """Return every user belonging to this organization."""
        stmt = select(User).where(User.organization_id == organization_id)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_member(
        self, organization_id: uuid.UUID, user_id: uuid.UUID
    ) -> User | None:
        """Return a single member of this organization, or None if not a member."""
        stmt = select(User).where(
            User.organization_id == organization_id, User.id == user_id
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_billing_managers(self, organization_id: uuid.UUID) -> list[User]:
        """Members who can act on this organization's billing (OWNER/ADMIN)
        — used to notify someone when a renewal charge fails, since that
        event isn't triggered by any particular user's action.
        """
        from app.modules.employer.enums import OrganizationRole

        stmt = select(User).where(
            User.organization_id == organization_id,
            User.organization_role.in_(
                [OrganizationRole.OWNER.value, OrganizationRole.ADMIN.value]
            ),
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def list_admin_users(self) -> list[User]:
        """Platform admins (role=ADMIN) — used to notify someone when a
        KYC submission needs review, since that event isn't triggered by
        any particular admin's action.
        """
        from app.modules.users.enums import UserRole

        stmt = select(User).where(User.role == UserRole.ADMIN.value)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_owners(self, organization_id: uuid.UUID) -> int:
        """Return how many OWNER-role members this organization currently has."""
        from app.modules.employer.enums import OrganizationRole

        stmt = select(func.count(User.id)).where(
            User.organization_id == organization_id,
            User.organization_role == OrganizationRole.OWNER.value,
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()
