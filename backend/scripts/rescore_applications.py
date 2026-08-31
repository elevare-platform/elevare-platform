"""One-off backfill: recompute match_score for every application that
already has one, now that EmbeddingAIService.compute_match_score actually
uses embeddings instead of silently falling back to keyword matching (see
docs/application-match-score-unification.md). Small, cheap — as of writing
only 19 applications have a match_score at all.

Run from inside the API container:
    python scripts/rescore_applications.py
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.ai.tasks import _compute_match_score_async
from app.modules.applications.models import Application


async def main() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            result = await db.execute(
                select(Application.id).where(Application.match_score.is_not(None))
            )
            application_ids = [row[0] for row in result.all()]
    finally:
        await engine.dispose()

    print(f"Rescoring {len(application_ids)} application(s)...")
    for application_id in application_ids:
        await _compute_match_score_async(str(application_id))
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
