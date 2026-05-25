"""Data-access layer for candidate profiles, CVs, and documents."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ProfileNotFoundException
from app.modules.candidates.models import (
    CandidateCvs,
    CandidateDocuments,
    CandidateProfile,
)
from app.modules.candidates.schema import UpdateProfileSchema

# Fields required for profile completion — single source of truth
REQUIRED_PROFILE_FIELDS = ("bio", "skills", "years_of_experience", "location")


def compute_profile_completion(profile: CandidateProfile) -> bool:
    """Return True if all required profile fields are populated."""
    return all(
        getattr(profile, field) not in ("", None, [], {})
        for field in REQUIRED_PROFILE_FIELDS
    )


class CandidateRepository:
    """Data-access layer for :class:`CandidateProfile`, :class:`CandidateCvs`, and :class:`CandidateDocuments`."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session.

        Args:
            db: The SQLAlchemy async session to use for all queries.

        """
        self._db = db

    async def get_by_user_id(self, user_id: uuid.UUID) -> CandidateProfile | None:
        """Fetch a candidate profile with CVs and documents eagerly loaded."""
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .options(
                selectinload(CandidateProfile.cvs),
                selectinload(CandidateProfile.documents),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, profile_id: uuid.UUID) -> CandidateProfile | None:
        """Fetch a candidate profile by its own PK."""
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.id == profile_id)
            .options(
                selectinload(CandidateProfile.cvs),
                selectinload(CandidateProfile.documents),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, user_id: uuid.UUID, data: UpdateProfileSchema) -> CandidateProfile:
        """Apply a partial update to a candidate profile and recompute completion.

        Args:
            user_id: UUID of the owning user.
            data: Validated partial-update payload.

        Returns:
            The updated :class:`CandidateProfile` instance.

        Raises:
            ProfileNotFoundException: If no profile exists for ``user_id``.

        """
        profile = await self.get_by_user_id(user_id)
        if profile is None:
            raise ProfileNotFoundException()

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(profile, key, value)

        profile.is_profile_complete = compute_profile_completion(profile)

        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def save_cv(self, profile_id: uuid.UUID, key: str, filename: str, is_default: bool) -> CandidateCvs:
        """Persist a new CV record and return it.

        Args:
            profile_id: The candidate profile UUID.
            key: Storage object key (e.g. S3/R2 path).
            filename: Original filename as uploaded by the user.
            is_default: Whether this CV should be the candidate's default.

        Returns:
            The newly created :class:`CandidateCvs` instance.

        """
        cv = CandidateCvs(
            candidate_id=profile_id,
            key=key,
            filename=filename,
            is_default=is_default,
        )
        self._db.add(cv)
        await self._db.flush()
        await self._db.refresh(cv)
        return cv

    async def has_any_cv(self, profile_id: uuid.UUID) -> bool:
        """Return True if the candidate has at least one CV on record."""
        stmt = select(CandidateCvs).where(CandidateCvs.candidate_id == profile_id).limit(1)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_cv(self, cv_id: uuid.UUID) -> CandidateCvs | None:
        """Fetch a single CV by its primary key, or None if not found."""
        return await self._db.get(CandidateCvs, cv_id)

    async def delete_cv(self, cv: CandidateCvs) -> None:
        """Delete a CV record and flush the session."""
        await self._db.delete(cv)
        await self._db.flush()

    async def promote_next_default_cv(self, profile_id: uuid.UUID) -> None:
        """After deleting the default CV, promote the most recent remaining one."""
        stmt = (
            select(CandidateCvs)
            .where(CandidateCvs.candidate_id == profile_id)
            .order_by(CandidateCvs.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(stmt)
        next_cv = result.scalar_one_or_none()
        if next_cv:
            next_cv.is_default = True
            await self._db.flush()

    async def set_default_cv(self, profile_id: uuid.UUID, cv_id: uuid.UUID) -> None:
        """Set one CV as default and clear the flag on all others.

        The DB partial unique index (one_default_cv_per_candidate) enforces
        that only one row per candidate can have is_default=TRUE at any time.
        We clear existing defaults first to avoid a constraint violation.
        """

        from sqlalchemy import update
        await self._db.execute(
            update(CandidateCvs)
            .where(CandidateCvs.candidate_id == profile_id)
            .values(is_default=False)
        )
        await self._db.execute(
            update(CandidateCvs)
            .where(CandidateCvs.id == cv_id)
            .values(is_default=True)
        )
        await self._db.flush()

    async def get_all_cvs(self, profile_id: uuid.UUID) -> list[CandidateCvs]:
        """Return all CVs belonging to a candidate profile."""
        result = await self._db.execute(
            select(CandidateCvs).where(CandidateCvs.candidate_id == profile_id)
        )
        return list(result.scalars().all())

    async def save_document(
        self, profile_id: uuid.UUID, key: str, filename: str, document_type: str
    ) -> CandidateDocuments:
        """Persist a new supporting document record and return it.

        Args:
            profile_id: The candidate profile UUID.
            key: Storage object key.
            filename: Original filename as uploaded by the user.
            document_type: MIME type or extension-derived type string.

        Returns:
            The newly created :class:`CandidateDocuments` instance.

        """
        doc = CandidateDocuments(
            candidate_id=profile_id,
            key=key,
            filename=filename,
            document_type=document_type,
        )
        self._db.add(doc)
        await self._db.flush()
        await self._db.refresh(doc)
        return doc

    async def get_document(self, document_id: uuid.UUID) -> CandidateDocuments | None:
        """Fetch a single document by its primary key, or None if not found."""
        return await self._db.get(CandidateDocuments, document_id)

    async def delete_document(self, document: CandidateDocuments) -> None:
        """Delete a document record and flush the session."""
        await self._db.delete(document)
        await self._db.flush()

    async def get_all_documents(self, profile_id: uuid.UUID) -> list[CandidateDocuments]:
        """Return all supporting documents belonging to a candidate profile."""
        result = await self._db.execute(
            select(CandidateDocuments).where(CandidateDocuments.candidate_id == profile_id)
        )
        return list(result.scalars().all())

    async def list_all(self) -> list[CandidateProfile]:
        """Return all candidate profiles with CVs and documents eagerly loaded."""
        result = await self._db.execute(
            select(CandidateProfile).options(
                selectinload(CandidateProfile.cvs),
                selectinload(CandidateProfile.documents),
            )
        )
        return list(result.scalars().all())

    async def count_cvs(self, profile_id: uuid.UUID) -> int:
        """Return the total number of CVs for a candidate profile."""
        result = await self._db.scalar(
            select(func.count()).where(CandidateCvs.candidate_id == profile_id)
        )
        return result or 0
