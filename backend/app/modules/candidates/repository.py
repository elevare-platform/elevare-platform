"""Data-access layer for candidate profiles, CVs, and documents."""

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ProfileNotFoundException
from app.core.pagination import paginate_cursor
from app.modules.applications.models import Application
from app.modules.candidates.models import (
    CandidateCvs,
    CandidateDocuments,
    CandidateProfile,
    Certification,
    Education,
    ProfileView,
    WorkExperience,
)
from app.modules.candidates.schema import (
    CertificationCreateSchema,
    EducationCreateSchema,
    UpdateProfileSchema,
    WorkExperienceCreateSchema,
)
from app.modules.users.models import User

logger = logging.getLogger(__name__)

# Fields required for profile completion — single source of truth
REQUIRED_PROFILE_FIELDS = ("bio", "skills", "years_of_experience", "location")


def compute_profile_completion(profile: CandidateProfile) -> bool:
    """Return True if all required profile fields are populated."""
    return all(
        getattr(profile, field) not in ("", None, [], {})
        for field in REQUIRED_PROFILE_FIELDS
    ) and len(profile.cvs) > 0


class CandidateRepository:
    """Data-access layer for :class:`CandidateProfile`, :class:`CandidateCvs`, and :class:`CandidateDocuments`."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session.

        Args:
        ----
            db: The SQLAlchemy async session to use for all queries.

        """
        self._db = db

    async def get_by_user_id(self, user_id: uuid.UUID) -> CandidateProfile | None:
        """Fetch a candidate profile with all related data eagerly loaded."""
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .options(
                selectinload(CandidateProfile.user),
                selectinload(CandidateProfile.cvs),
                selectinload(CandidateProfile.documents),
                selectinload(CandidateProfile.work_experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.certifications),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: uuid.UUID | None = None,
        skills: list[str] | None = None,
        years_of_experience: int | None = None,
        linkedin_url: str | None = None,
    ) -> CandidateProfile:
        """Create a new candidate profile, optionally linked to a user account."""
        profile = CandidateProfile(
            user_id=user_id,
            skills=skills,
            years_of_experience=years_of_experience,
            linkedin_url=linkedin_url,
        )
        self._db.add(profile)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def get_by_id(self, profile_id: uuid.UUID) -> CandidateProfile | None:
        """Fetch a candidate profile by its own PK."""
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.id == profile_id)
            .options(
                selectinload(CandidateProfile.cvs),
                selectinload(CandidateProfile.documents),
                selectinload(CandidateProfile.user).selectinload(User.applications).selectinload(Application.job),
                selectinload(CandidateProfile.work_experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.certifications),
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, user_id: uuid.UUID, data: UpdateProfileSchema) -> CandidateProfile:
        """Apply a partial update to a candidate profile and recompute completion.

        Args:
        ----
            user_id: UUID of the owning user.
            data: Validated partial-update payload.

        Returns:
        -------
            The updated :class:`CandidateProfile` instance.

        Raises:
        ------
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
        ----
            profile_id: The candidate profile UUID.
            key: Storage object key (e.g. S3/R2 path).
            filename: Original filename as uploaded by the user.
            is_default: Whether this CV should be the candidate's default.

        Returns:
        -------
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
        ----
            profile_id: The candidate profile UUID.
            key: Storage object key.
            filename: Original filename as uploaded by the user.
            document_type: MIME type or extension-derived type string.

        Returns:
        -------
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
                selectinload(CandidateProfile.user),
                selectinload(CandidateProfile.cvs),
                selectinload(CandidateProfile.documents),
                selectinload(CandidateProfile.work_experiences),
                selectinload(CandidateProfile.educations),
                selectinload(CandidateProfile.certifications),
            )
        )
        return list(result.scalars().all())

    async def count_cvs(self, profile_id: uuid.UUID) -> int:
        """Return the total number of CVs for a candidate profile."""
        result = await self._db.scalar(
            select(func.count()).where(CandidateCvs.candidate_id == profile_id)
        )
        return result or 0

    # ------------------------------------------------------------------
    # Work Experience
    # ------------------------------------------------------------------

    async def add_work_experience(
        self, profile_id: uuid.UUID, data: WorkExperienceCreateSchema
    ) -> WorkExperience:
        """Persist a new work experience entry."""
        entry = WorkExperience(candidate_id=profile_id, **data.model_dump())
        self._db.add(entry)
        await self._db.flush()
        await self._db.refresh(entry)
        return entry

    async def get_work_experience(self, entry_id: uuid.UUID) -> WorkExperience | None:
        """Fetch a single work experience entry by its primary key, or None if not found."""
        return await self._db.get(WorkExperience, entry_id)

    async def delete_work_experience(self, entry: WorkExperience) -> None:
        """Delete a work experience record and flush the session."""
        await self._db.delete(entry)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Education
    # ------------------------------------------------------------------

    async def add_education(
        self, profile_id: uuid.UUID, data: EducationCreateSchema
    ) -> Education:
        """Persist a new education entry."""
        entry = Education(candidate_id=profile_id, **data.model_dump())
        self._db.add(entry)
        await self._db.flush()
        await self._db.refresh(entry)
        return entry

    async def get_education(self, entry_id: uuid.UUID) -> Education | None:
        """Fetch a single education entry by its primary key, or None if not found."""
        return await self._db.get(Education, entry_id)

    async def delete_education(self, entry: Education) -> None:
        """Delete an education record and flush the session."""
        await self._db.delete(entry)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    async def add_certification(
        self, profile_id: uuid.UUID, data: CertificationCreateSchema
    ) -> Certification:
        """Persist a new certification entry."""
        entry = Certification(candidate_id=profile_id, **data.model_dump())
        self._db.add(entry)
        await self._db.flush()
        await self._db.refresh(entry)
        return entry

    async def get_certification(self, entry_id: uuid.UUID) -> Certification | None:
        """Fetch a single certification entry by its primary key, or None if not found."""
        return await self._db.get(Certification, entry_id)

    async def delete_certification(self, entry: Certification) -> None:
        """Delete a certification record and flush the session."""
        await self._db.delete(entry)
        await self._db.flush()


    # -----------------------------------------------
    # Privacy — application check for APPLIED_ONLY
    # -----------------------------------------------

    async def candidate_has_applied_to_employer(
        self,
        candidate_profile_id: uuid.UUID,
        employer_id: uuid.UUID,
    ) -> bool:
        """Return True if the candidate has applied to any job owned by this employer."""
        from sqlalchemy import and_

        from app.modules.applications.models import Application
        from app.modules.jobs.models import Job

        stmt = (
            select(Application.id)
            .join(Job, Job.id == Application.job_id)
            .join(CandidateProfile, CandidateProfile.user_id == Application.candidate_id)
            .where(
                and_(
                    CandidateProfile.id == candidate_profile_id,
                    Job.employer_id == employer_id,
                )
            )
            .limit(1)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none() is not None

    # -----------------------------------------------
    # Profile Views
    # -----------------------------------------------

    _VIEW_DEDUP_HOURS = 24

    async def create_profile_viewed(
        self,
        employer_id: uuid.UUID,
        candidate_profile_id: uuid.UUID,
        job_id: uuid.UUID | None = None,
    ) -> ProfileView | None:
        """Record that an employer viewed a candidate's profile.

        Returns None (no insert) if the same employer already viewed this
        candidate+job combination within the last 24 hours — prevents a
        single browsing session from flooding the candidate's view history.
        """
        from datetime import timedelta

        from sqlalchemy import and_

        cutoff = func.now() - timedelta(hours=self._VIEW_DEDUP_HOURS)

        dupe_stmt = select(ProfileView).where(
            and_(
                ProfileView.employer_id == employer_id,
                ProfileView.candidate_id == candidate_profile_id,
                ProfileView.job_id == job_id,  # works for both UUID and None
                ProfileView.viewed_at >= cutoff,
            )
        ).limit(1)

        result = await self._db.execute(dupe_stmt)
        if result.scalar_one_or_none() is not None:
            return None  # already recorded recently, skip

        #TODO: In app notification
        logger.info("Candidate profile viewed")
        profile_viewed = ProfileView(
            candidate_id=candidate_profile_id,
            employer_id=employer_id,
            job_id=job_id,
        )
        self._db.add(profile_viewed)
        await self._db.flush()
        return profile_viewed

    async def get_profile_views(
        self,
        candidate_profile_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 20,
    ):
        """Return paginated profile view records for a candidate."""
        stmt = (
            select(ProfileView)
            .where(ProfileView.candidate_id == candidate_profile_id)
            .options(
                selectinload(ProfileView.employer).selectinload(User.employer_profile)
            )
        )
        return await paginate_cursor(stmt, self._db, cursor, limit)
