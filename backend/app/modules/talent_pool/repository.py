"""Data-access layer for TalentPoolProfiles."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import paginate_cursor
from app.modules.candidates.models import CandidateProfile
from app.modules.talent_pool.enums import SourceType
from app.modules.talent_pool.models import TalentPoolProfiles
from app.modules.users.enums import UserRole


class TalentPoolRepository:
    """Handles all database operations for TalentPoolProfiles."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._db = db

    async def create(self, profile_data: dict) -> TalentPoolProfiles:
        """Create a new talent pool profile and return it."""
        profile = TalentPoolProfiles(**profile_data)
        self._db.add(profile)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def get_by_id(
        self,
        profile_id: uuid.UUID,
    ) -> TalentPoolProfiles | None:
        """Fetch a talent pool profile by its primary key, or None if not found."""
        result = await self._db.execute(
            select(TalentPoolProfiles).where(TalentPoolProfiles.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_by_candidate_profile_id(
        self,
        candidate_profile_id: uuid.UUID,
    ) -> TalentPoolProfiles | None:
        """Fetch the (unique) talent pool profile linked to a self-registered candidate.

        Every self-registered candidate gets exactly one row here at
        registration — this is the bridge from a `candidate_profile_id`
        (e.g. on an Application) to the id everything else in the talent
        pool / introductions / saved-candidates system actually keys on.
        """
        result = await self._db.execute(
            select(TalentPoolProfiles).where(
                TalentPoolProfiles.candidate_profile_id == candidate_profile_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _visible_to(stmt, viewer_id: uuid.UUID | None, is_admin: bool):
        """Non-admins see only the entries they uploaded and the ones admins added; admins see
        everything. An email typed in only to send an interview to has no CV and is never part
        of the Talent Pool page."""
        if not is_admin and viewer_id:
            from sqlalchemy import or_

            from app.modules.users.enums import UserRole
            from app.modules.users.models import User as UserModel

            # Subquery: is the added_by user an admin?
            admin_subq = (
                select(UserModel.id)
                .where(UserModel.id == TalentPoolProfiles.added_by)
                .where(UserModel.role == UserRole.ADMIN.value)
                .correlate(TalentPoolProfiles)
                .exists()
            )
            stmt = stmt.where(
                or_(
                    TalentPoolProfiles.added_by == viewer_id,
                    admin_subq,
                )
            )
        return stmt.where(TalentPoolProfiles.source != SourceType.INTERVIEW_INVITE.value)

    @staticmethod
    def _only_unseen(stmt, viewer_id: uuid.UUID, baseline: datetime):
        """Keep the CVs added after the viewer's baseline that the viewer has not opened."""
        from app.modules.seen.models import TalentPoolProfileView

        opened = (
            select(TalentPoolProfileView.id)
            .where(TalentPoolProfileView.talent_pool_profile_id == TalentPoolProfiles.id)
            .where(TalentPoolProfileView.employer_id == viewer_id)
            .correlate(TalentPoolProfiles)
            .exists()
        )
        return stmt.where(TalentPoolProfiles.created_at > baseline).where(~opened)

    async def count_unseen(
        self, viewer_id: uuid.UUID, is_admin: bool, baseline: datetime
    ) -> int:
        """How many CVs the viewer can see that were added after their baseline and not opened."""
        stmt = self._only_unseen(
            self._visible_to(select(func.count()).select_from(TalentPoolProfiles), viewer_id, is_admin),
            viewer_id,
            baseline,
        )
        return (await self._db.execute(stmt)).scalar_one()

    async def visible_profile_exists(
        self, profile_id: uuid.UUID, viewer_id: uuid.UUID, is_admin: bool
    ) -> bool:
        """Whether this CV is one the viewer may see (the same rule as the list)."""
        stmt = self._visible_to(
            select(TalentPoolProfiles.id).where(TalentPoolProfiles.id == profile_id), viewer_id, is_admin
        )
        return (await self._db.execute(stmt)).scalar_one_or_none() is not None

    async def find_interview_invite(
        self, employer_id: uuid.UUID, email: str
    ) -> uuid.UUID | None:
        """The id of the email-only row this employer made for ``email`` (lower case) before, so
        typing the same address again never makes a second one."""
        result = await self._db.execute(
            select(TalentPoolProfiles.id)
            .where(TalentPoolProfiles.source == SourceType.INTERVIEW_INVITE.value)
            .where(TalentPoolProfiles.added_by == employer_id)
            .where(func.lower(TalentPoolProfiles.override_email) == email)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id_joined_with_other_data(
        self,
        profile_id: uuid.UUID,
    ) -> TalentPoolProfiles | None:
        """Fetch a talent pool profile joined with its parsed submission by primary key."""
        from sqlalchemy.orm import selectinload

        result = await self._db.execute(
            select(TalentPoolProfiles)
            .where(TalentPoolProfiles.id == profile_id)
            .options(selectinload(TalentPoolProfiles.added_by_user))
            .options(selectinload(TalentPoolProfiles.parsed_submission))
            .options(
                selectinload(TalentPoolProfiles.candidate_profile).selectinload(
                    CandidateProfile.user
                )
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        status: str | None = None,
        source: str | None = None,
        job_id: uuid.UUID | None = None,
        cursor: str | None = None,
        limit: int = 20,
        viewer_id: uuid.UUID | None = None,
        is_admin: bool = False,
        added_within_days: int | None = None,
        min_score: int | None = None,
        sort: str | None = None,
        unseen_since: datetime | None = None,
    ) -> dict:
        """Return paginated talent pool profiles with optional filters.

        Non-admins only see entries they uploaded or entries added by admins.
        When ``job_id`` is provided, results are ordered by ai_score descending.
        ``unseen_since`` (the viewer's baseline) keeps only the CVs added after it that the
        viewer has not opened.
        """

        stmt = self._visible_to(select(TalentPoolProfiles), viewer_id, is_admin)
        if unseen_since is not None and viewer_id:
            stmt = self._only_unseen(stmt, viewer_id, unseen_since)

        if status:
            stmt = stmt.where(TalentPoolProfiles.status == status)
        if source:
            stmt = stmt.where(TalentPoolProfiles.source == source)
        if job_id:
            stmt = stmt.where(TalentPoolProfiles.sourced_for_job_id == job_id)
        if added_within_days:
            cutoff = datetime.now(UTC) - timedelta(days=added_within_days)
            stmt = stmt.where(TalentPoolProfiles.created_at >= cutoff)
        if min_score is not None:
            stmt = stmt.where(TalentPoolProfiles.ai_score >= min_score)

        use_score = (sort or ("score" if job_id else "newest")) == "score"
        sort_column = "ai_score" if use_score else None
        return await paginate_cursor(
            stmt, self._db, cursor, limit, sort_column=sort_column
        )

    async def update(
        self, profile_id: uuid.UUID, data: dict
    ) -> TalentPoolProfiles | None:
        """Apply a partial update dict to a profile and return it, or None if not found."""
        profile = await self.get_by_id(profile_id)
        if not profile:
            return None
        for key, value in data.items():
            setattr(profile, key, value)
        await self._db.flush()
        await self._db.refresh(profile)
        return profile

    async def list_unscored_for_job(self, job_id: uuid.UUID):
        """Return profiles with a parsed submission that haven't been scored against this job yet.

        Includes profiles already sourced for this job that haven't been scored yet,
        plus pipeline profiles (no job) that can be scored retroactively.
        """
        from sqlalchemy import or_

        stmt = (
            select(TalentPoolProfiles)
            .where(TalentPoolProfiles.parsed_submission_id.is_not(None))
            .where(
                or_(
                    TalentPoolProfiles.sourced_for_job_id == job_id,
                    TalentPoolProfiles.sourced_for_job_id.is_(None),
                )
            )
            .where(TalentPoolProfiles.ai_score.is_(None))
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def find_matches_for_job(
        self,
        job_embedding: list[float],
        employer_id: uuid.UUID,
        exclude_user_ids: list[uuid.UUID],
        limit: int = 20,
    ) -> list[tuple[TalentPoolProfiles, float]]:
        """Return talent pool profiles ranked by embedding similarity to a job.

        Covers both sourced profiles (no candidate_profile_id) and self-registered
        candidates. cv_sharing_consent is only checked for self-registered candidates.
        Profiles whose linked candidate user has already applied are excluded.
        """
        from sqlalchemy.orm import selectinload

        from app.modules.ai.enums import CVParsingStatus
        from app.modules.ai.models import ParsedCVSubmission
        from app.modules.candidates.models import CandidateProfile

        await self._db.execute(text("SET ivfflat.probes = 10"))

        distance = TalentPoolProfiles.profile_embedding.cosine_distance(job_embedding)

        from app.modules.users.models import User as UserModel

        # Correlated subquery: is the profile's uploader an admin?
        admin_subq = (
            select(UserModel.id)
            .where(UserModel.id == TalentPoolProfiles.added_by)
            .where(UserModel.role == UserRole.ADMIN.value)
            .correlate(TalentPoolProfiles)
            .exists()
        )

        stmt = (
            select(TalentPoolProfiles, distance.label("distance"))
            .outerjoin(
                CandidateProfile,
                TalentPoolProfiles.candidate_profile_id == CandidateProfile.id,
            )
            .outerjoin(
                ParsedCVSubmission,
                TalentPoolProfiles.parsed_submission_id == ParsedCVSubmission.id,
            )
            .where(TalentPoolProfiles.profile_embedding.is_not(None))
            # Visibility + ownership in one expression:
            # - Self-registered (candidate_profile_id IS NOT NULL): require cv_sharing_consent
            # - Sourced (candidate_profile_id IS NULL): only show if added by this employer OR an admin,
            #   AND the CV parse actually completed cleanly — a FLAGGED/FAILED/PENDING
            #   parse means low-confidence extraction, non-English, scanned/OCR, or the
            #   document not being a real CV at all (e.g. a presentation or unrelated
            #   PDF mistakenly uploaded). Those still get an embedding generated from
            #   whatever text WAS extracted and can score deceptively well due to
            #   embedding-model anisotropy — exclude them at the source instead of
            #   trying to catch it downstream in scoring.
            .where(
                sa.or_(
                    sa.and_(
                        TalentPoolProfiles.candidate_profile_id.is_not(None),
                        CandidateProfile.cv_sharing_consent.is_(True),
                    ),
                    sa.and_(
                        TalentPoolProfiles.candidate_profile_id.is_(None),
                        sa.or_(
                            TalentPoolProfiles.added_by == employer_id,
                            admin_subq,
                        ),
                        ParsedCVSubmission.parse_status
                        == CVParsingStatus.COMPLETED.value,
                    ),
                )
            )
            .options(
                selectinload(TalentPoolProfiles.parsed_submission),
                selectinload(TalentPoolProfiles.candidate_profile).selectinload(
                    CandidateProfile.user
                ),
            )
        )

        if exclude_user_ids:
            stmt = stmt.where(
                sa.or_(
                    CandidateProfile.user_id.is_(None),
                    CandidateProfile.user_id.not_in(exclude_user_ids),
                )
            )

        stmt = stmt.order_by(distance.asc()).limit(limit)

        result = await self._db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def find_candidates_for_search(
        self,
        employer_id: uuid.UUID,
        query_embedding: list[float] | None = None,
        limit: int = 50,
    ) -> list[tuple[TalentPoolProfiles, float | None]]:
        """Return talent pool profiles for employer-facing candidate search.

        This is the same table and the same visibility/ownership rule as
        ``find_matches_for_job`` — covers both self-registered candidates and
        employer-sourced CVs — just entered from a free-text/filter search
        instead of a specific job. Unlike job matching, ``query_embedding``
        is optional: with no free-text query there's nothing to rank by
        distance, so results come back in recency order instead and the
        caller applies filters/scoring in Python (mirroring
        ``get_top_matches_for_job``'s overfetch-then-filter approach).
        """
        from sqlalchemy.orm import selectinload

        from app.modules.ai.enums import CVParsingStatus
        from app.modules.ai.models import ParsedCVSubmission
        from app.modules.candidates.models import CandidateProfile
        from app.modules.users.models import User as UserModel

        distance = None
        select_cols = [TalentPoolProfiles]
        if query_embedding is not None:
            await self._db.execute(text("SET ivfflat.probes = 10"))
            distance = TalentPoolProfiles.profile_embedding.cosine_distance(
                query_embedding
            )
            select_cols.append(distance.label("distance"))

        admin_subq = (
            select(UserModel.id)
            .where(UserModel.id == TalentPoolProfiles.added_by)
            .where(UserModel.role == UserRole.ADMIN.value)
            .correlate(TalentPoolProfiles)
            .exists()
        )

        stmt = (
            select(*select_cols)
            .outerjoin(
                CandidateProfile,
                TalentPoolProfiles.candidate_profile_id == CandidateProfile.id,
            )
            .outerjoin(
                ParsedCVSubmission,
                TalentPoolProfiles.parsed_submission_id == ParsedCVSubmission.id,
            )
            # Same visibility + ownership rule as find_matches_for_job:
            # - Self-registered: require cv_sharing_consent
            # - Sourced: only added-by-this-employer or an admin, and parsed cleanly
            .where(
                sa.or_(
                    sa.and_(
                        TalentPoolProfiles.candidate_profile_id.is_not(None),
                        CandidateProfile.cv_sharing_consent.is_(True),
                    ),
                    sa.and_(
                        TalentPoolProfiles.candidate_profile_id.is_(None),
                        sa.or_(
                            TalentPoolProfiles.added_by == employer_id,
                            admin_subq,
                        ),
                        ParsedCVSubmission.parse_status
                        == CVParsingStatus.COMPLETED.value,
                    ),
                )
            )
            .options(
                selectinload(TalentPoolProfiles.parsed_submission),
                selectinload(TalentPoolProfiles.candidate_profile).selectinload(
                    CandidateProfile.user
                ),
                selectinload(TalentPoolProfiles.candidate_profile).selectinload(
                    CandidateProfile.work_experiences
                ),
            )
        )

        if query_embedding is not None:
            stmt = stmt.where(TalentPoolProfiles.profile_embedding.is_not(None))
            stmt = stmt.order_by(distance.asc())
        else:
            stmt = stmt.order_by(TalentPoolProfiles.created_at.desc())

        stmt = stmt.limit(limit)
        result = await self._db.execute(stmt)

        if query_embedding is not None:
            return [(row[0], row[1]) for row in result.all()]
        return [(row, None) for row in result.scalars().all()]
