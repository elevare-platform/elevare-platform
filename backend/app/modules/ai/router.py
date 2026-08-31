from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cost_trend import build_flat_series
from app.core.dependencies import get_db, require_role
from app.modules.ai.enums import JobDescriptionMode
from app.modules.ai.repository import AIRepository
from app.modules.ai.schema import (
    JobDescriptionRequest,
    JobDescriptionResponse,
    MatchRequest,
    MatchResult,
)
from app.modules.ai.service import get_ai_service
from app.modules.candidates.repository import CandidateRepository
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import build_full_description
from app.modules.users.models import User

router = APIRouter()


@router.get("/fit-scoring/costs", status_code=200)
async def get_fit_scoring_costs(
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return the current month's LLM cost summary for candidate-vs-job fit
    scoring (Application and talent-pool "score against job" flows). Admin only.
    """
    now = datetime.now(UTC)
    row = await AIRepository(db).get_monthly_fit_scoring_cost_summary()
    return {
        "month": now.strftime("%Y-%m"),
        "total_cost_usd": float(row.total_cost) if row.total_cost is not None else None,
        "total_llm_calls": row.total_calls or 0,
    }


@router.get("/fit-scoring/costs/trend", status_code=200)
async def get_fit_scoring_costs_trend(
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    current_user: User = Depends(require_role("ADMIN")),
    db: AsyncSession = Depends(get_db),
):
    """Return a monthly fit-scoring cost/call trend, optionally bounded by
    ?from=&to= (YYYY-MM-DD). Omit both for the full history. Admin only."""
    rows = await AIRepository(db).get_fit_scoring_cost_trend(from_date, to_date)
    return {"series": build_flat_series(rows, from_date, to_date)}

# Modes that require existing text to operate on
_MODES_REQUIRING_TEXT = {
    JobDescriptionMode.IMPROVE,
    JobDescriptionMode.SHORTEN,
    JobDescriptionMode.EXPAND,
    JobDescriptionMode.REWRITE_PROFESSIONAL,
    JobDescriptionMode.MORE_INCLUSIVE,
    JobDescriptionMode.IMPROVE_CLARITY,
}


@router.post("/match", status_code=200, response_model=MatchResult)
async def ai_match(
    data: MatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "EMPLOYER")),
) -> MatchResult:
    """On-demand match score between a candidate and a job.

    Returns a fresh MatchResult. Does not overwrite the stored score
    on the application row — use this for display only.
    """
    candidate = await CandidateRepository(db).get_by_user_id(data.candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    job = await JobRepository(db).get_by_id(data.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    ai_service = get_ai_service()
    return await ai_service.compute_match_score(
        candidate.skills or [],
        build_full_description(
            about_the_role=job.about_the_role,
            key_responsibilities=job.key_responsibilities,
            requirements=job.requirements,
            preferred_certifications=job.preferred_certifications,
            technical_competencies=job.technical_competencies,
            what_we_offer=job.what_we_offer,
            legacy_description=job.description,
        ),
        job.title or "",
        job.required_skills or [],
        candidate_embedding=candidate.profile_embedding,
        job_embedding=job.job_embedding,
    )


@router.post("/job-description", status_code=200, response_model=JobDescriptionResponse)
async def ai_job_description(
    data: JobDescriptionRequest,
    current_user: User = Depends(require_role("EMPLOYER")),
) -> JobDescriptionResponse:
    """Generate or improve a job description field using AI.

    GENERATE mode builds text from scratch using job_context.
    All other modes require current_text to be non-empty.
    Only EMPLOYER-role users may call this endpoint.
    """
    if data.mode in _MODES_REQUIRING_TEXT and not (
        data.current_text and data.current_text.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail=f"current_text is required for mode {data.mode.value}",
        )

    ai_service = get_ai_service()
    generated_text = await ai_service.generate_job_description_text(
        mode=data.mode.value,
        field=data.field.value,
        current_text=data.current_text,
        job_context=data.job_context,
    )

    return JobDescriptionResponse(
        generated_text=generated_text,
        mode=data.mode,
        field=data.field,
    )
