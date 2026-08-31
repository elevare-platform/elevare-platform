"""Candidate-facing job matches endpoint — Phase 18.

Queries open jobs ranked by embedding similarity against the candidate's
stored profile_embedding. Respects existing visibility rules — only public
job fields are returned (same JobResponse used on the job board).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.dependencies import get_db, require_role
from app.modules.jobs.enums import JobStatus, ModerationStatus
from app.modules.jobs.models import Job
from app.modules.jobs.schemas import JobResponse
from app.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


class JobMatchResult(BaseModel):
    """A single job match with its similarity score and matched skills."""

    job: JobResponse
    similarity_score: int  # 0–100
    matched_skills: list[str] = []  # candidate skills that match job requirements

    @model_validator(mode="after")
    def strip_internal_employer_fields(self) -> "JobMatchResult":
        """Remove personal employer contact info — not needed on the candidate matches view."""
        self.job.employer_email = None
        self.job.employer_phone = None
        self.job.employer_first_name = None
        self.job.employer_last_name = None
        return self


@router.get("/me/matches", response_model=list[JobMatchResult])
async def get_my_job_matches(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("CANDIDATE")),
):
    """Return open jobs ranked by embedding similarity to the candidate's profile.

    Only ACTIVE + APPROVED jobs are returned. All fields come from the existing
    public JobResponse — no internal employer data is leaked beyond what the
    job board already shows.
    """
    from app.modules.candidates.repository import CandidateRepository

    candidate_repo = CandidateRepository(db)
    profile = await candidate_repo.get_by_user_id(current_user.id)

    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    if profile.profile_embedding is None or len(profile.profile_embedding) == 0:
        return []

    # Tune recall — same as talent match
    await db.execute(text("SET ivfflat.probes = 10"))

    embedding = profile.profile_embedding
    distance = Job.job_embedding.cosine_distance(embedding)

    stmt = (
        select(Job, distance.label("distance"))
        .where(Job.job_embedding.is_not(None))
        .where(Job.status == JobStatus.ACTIVE.value)
        .where(Job.moderation_status == ModerationStatus.APPROVED.value)
        .options(selectinload(Job.employer).selectinload(User.organization))
        .order_by(distance.asc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    candidate_skills_lower = {s.lower(): s for s in (profile.skills or [])}

    matches = []
    for job, dist in rows:
        similarity = max(0, min(100, round((1 - dist / 2) * 100)))
        matched = [
            candidate_skills_lower[s.lower()]
            for s in (job.required_skills or [])
            if s.lower() in candidate_skills_lower
        ][:3]
        matches.append(
            JobMatchResult(
                job=JobResponse.from_job(job, include_interview_brief=False, include_contact_info=False),
                similarity_score=similarity,
                matched_skills=matched,
            )
        )

    return matches
