import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ai.models import FitScoringCost, ParsedCVSubmission


class AIRepository:
    """Data-access layer for ParsedCVSubmission records."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialise the repository with an async database session."""
        self._db = db

    async def get_submission_by_id(
        self, submission_id: uuid.UUID
    ) -> ParsedCVSubmission | None:
        """Fetch a parsed CV submission by its primary key, or None if not found."""
        result = await self._db.execute(
            select(ParsedCVSubmission).where(ParsedCVSubmission.id == submission_id)
        )
        return result.scalar_one_or_none()

    async def create_fit_scoring_cost_row(
        self,
        *,
        job_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal | None,
        model: str,
        application_id: uuid.UUID | None = None,
        talent_pool_profile_id: uuid.UUID | None = None,
    ) -> FitScoringCost:
        """Record the token cost for one LLM fit-reasoning call."""
        cost_row = FitScoringCost(
            job_id=job_id,
            application_id=application_id,
            talent_pool_profile_id=talent_pool_profile_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            model=model,
        )
        self._db.add(cost_row)
        await self._db.flush()
        return cost_row

    async def get_monthly_fit_scoring_cost_summary(self):
        """Return aggregated total cost and call count for the current calendar month."""
        result = await self._db.execute(
            select(
                func.sum(FitScoringCost.cost_usd).label("total_cost"),
                func.count(FitScoringCost.id).label("total_calls"),
            ).where(
                func.date_trunc("month", FitScoringCost.created_at)
                == func.date_trunc("month", func.now())
            )
        )
        return result.one()

    async def get_fit_scoring_cost_trend(
        self, from_date: date | None, to_date: date | None
    ):
        """Return per-month cost/call totals for fit-scoring, optionally
        bounded by [from_date, to_date] (inclusive on both ends)."""
        month_col = func.date_trunc("month", FitScoringCost.created_at)
        stmt = (
            select(
                month_col.label("month"),
                func.sum(FitScoringCost.cost_usd).label("total_cost"),
                func.count(FitScoringCost.id).label("total_calls"),
            )
            .group_by(month_col)
            .order_by(month_col)
        )
        if from_date:
            stmt = stmt.where(FitScoringCost.created_at >= from_date)
        if to_date:
            stmt = stmt.where(FitScoringCost.created_at < to_date + timedelta(days=1))
        result = await self._db.execute(stmt)
        return result.all()
