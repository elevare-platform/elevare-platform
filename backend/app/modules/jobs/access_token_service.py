"""Service layer for job access tokens and public applicant views."""
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    JobNotFoundError,
    PermissionDeniedException,
    TokenNotFoundError,
)
from app.modules.applications.repository import ApplicationRepository
from app.modules.applications.schema import ApplicationFilters
from app.modules.jobs.access_token_repository import AccessTokenRepository
from app.modules.jobs.access_token_schema import (
    AccessTokenResponse,
    CreateAccessTokenRequest,
    PublicApplicantsItem,
    PublicApplicantsResponse,
)
from app.modules.jobs.repository import JobRepository
from app.modules.users.enums import UserRole
from app.modules.users.models import User

logger = logging.getLogger(__name__)


class AccessTokenService:
    """Manages creation, retrieval, revocation, and public applicant views for job access tokens."""

    def __init__(self, db: AsyncSession):
        """Initialise with an async database session."""
        self._db = db
        self._repo = AccessTokenRepository(db)
        self._job_repo = JobRepository(db)
        self._app_repo = ApplicationRepository(db)

    async def create_access_token(
        self, job_id: uuid.UUID,
        data: CreateAccessTokenRequest,
        current_user: User,
    ) -> AccessTokenResponse:
        """Create a shareable access token for a job's applicant list.

        Raises:
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job.

        """
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
        current_user: User,
    ) -> list[AccessTokenResponse]:
        """Return all access tokens for a job.

        Raises:
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job.

        """
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
        current_user: User,
    ):
        """Delete an access token.

        Raises:
            JobNotFoundError: If the job does not exist.
            PermissionDeniedException: If the caller does not own the job.
            TokenNotFoundError: If the token does not exist.

        """
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
        current_user: User,
    ) -> AccessTokenResponse:
        """Revoke an access token immediately.

        Raises:
            TokenNotFoundError: If the token does not exist.
            PermissionDeniedException: If the caller does not own the job.

        """
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
        token_str: str,
    ) -> PublicApplicantsResponse:
        """Return ranked applicants for a public shared link.

        Combines platform applicants and externally uploaded CV profiles,
        sorted by AI score descending. Returns 404 for invalid/expired tokens.
        """
        token = await self._repo.get_valid_by_token(token_str)

        if not token:
            raise JobNotFoundError()

        job = await self._job_repo.get_by_id(token.job_id)

        # ── 1. Platform applicants ──────────────────────────────────────────
        paginated = await self._app_repo.get_job_applicants(
            job_id=token.job_id,
            filters=ApplicationFilters(sort="ai_score"),
            limit=200,
            cursor=None,
        )

        combined: list[PublicApplicantsItem] = []

        for application in paginated["items"]:
            candidate = application.candidate
            candidate_profile = getattr(candidate, "candidate_profile", None)

            first = candidate.first_name or ""
            last = candidate.last_name or ""
            initials = f"{first[:1]}{last[:1]}".upper()

            # Name gate: token-level AND per-candidate consent
            full_name = None
            if (
                token.disclose_names
                and candidate_profile
                and candidate_profile.cv_sharing_consent
            ):
                full_name = f"{first} {last}".strip()

            cv_snippet = None
            cv = getattr(application, "cv", None)
            if cv and hasattr(cv, "submission") and cv.submission:
                summary = (cv.submission.parsed_data or {}).get("summary") or ""
                cv_snippet = summary[:200] if summary else None

            combined.append(PublicApplicantsItem(
                initials=initials,
                full_name=full_name,
                ai_score=application.ai_score,
                ai_fit_summary=application.ai_fit_summary,
                ai_strengths=application.ai_strengths,
                ai_weaknesses=application.ai_weaknesses,
                cv_snippet=cv_snippet,
                source="applicant",
            ))

        # ── 2. External talent pool profiles scored against this job ────────
        from sqlalchemy import select

        from app.modules.ai.repository import AIRepository
        from app.modules.talent_pool.models import TalentPoolProfiles

        ai_repo = AIRepository(self._db)
        tp_result = await self._db.execute(
            select(TalentPoolProfiles)
            .where(TalentPoolProfiles.sourced_for_job_id == token.job_id)
            .where(TalentPoolProfiles.ai_score.is_not(None))
        )
        pool_profiles = list(tp_result.scalars().all())

        for profile in pool_profiles:
            parsed_data = {}
            if profile.parsed_submission_id:
                submission = await ai_repo.get_submission_by_id(profile.parsed_submission_id)
                if submission and submission.parsed_data:
                    parsed_data = submission.parsed_data

            full_name_raw = parsed_data.get("full_name") or (
                f"{parsed_data.get('first_name', '')} {parsed_data.get('last_name', '')}".strip() or None
            )
            # Initials from parsed name, fall back to "EX" (external)
            initials = (
                "".join(w[0].upper() for w in (full_name_raw or "").split()[:2])
                or "EX"
            )
            # External CVs: always initials-only on shared links.
            # These candidates have no relationship with Elevare and gave no consent.
            # Token-level disclosure does not override this — only platform candidates
            # with cv_sharing_consent=True can have their name disclosed.
            full_name = None

            summary = parsed_data.get("summary") or ""
            cv_snippet = summary[:200] if summary else None

            combined.append(PublicApplicantsItem(
                initials=initials,
                full_name=full_name,
                ai_score=profile.ai_score,
                ai_fit_summary=profile.ai_fit_summary,
                ai_strengths=profile.ai_strengths,
                ai_weaknesses=profile.ai_weaknesses,
                cv_snippet=cv_snippet,
                source="external",
            ))

        # ── 3. Merge and rank by ai_score descending, nulls last ────────────
        combined.sort(
            key=lambda x: (x.ai_score is None, -(x.ai_score or 0))
        )

        return PublicApplicantsResponse(
            job_title=job.title,
            expires_at=token.expires_at,
            applicants=combined,
        )

