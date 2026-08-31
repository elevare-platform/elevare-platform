"""
One-off script: re-run AI scoring for interviews that already have a
transcript, without re-downloading/re-transcribing the recording.

Use this when scoring failed or fell back to score=0 for a reason unrelated
to transcription (e.g. a bad ANTHROPIC_API_KEY) — the transcript is already
saved, only the LLM scoring call needs to be redone.

Usage (from the api container, which has the app's Python env and network
access to Anthropic):

    docker-compose exec api python scripts/rescore_interview.py \\
        74a600bc-3026-4b50-90ef-e4d582ecf0ad \\
        a87fa3f6-6ac1-4326-8948-0e425eb4ebae \\
        a1b2d122-f7c8-4065-9231-8f7bee3c05ed
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.core.model_registry  # noqa: F401 — ensures all mappers are registered before any DB use
from app.core.config import settings
from app.modules.ai.service import AnthropicCVExtractionService
from app.modules.interviews.repository import InterviewRepository


async def rescore_one(db, repo: InterviewRepository, interview_id: uuid.UUID) -> None:
    interview = await repo.get_by_id(interview_id)
    if interview is None:
        print(f"  SKIP {interview_id}: not found")
        return
    if not interview.transcript:
        print(f"  SKIP {interview_id}: no transcript saved yet")
        return

    job = interview.job
    job_context_parts = [
        f"Title: {job.title}",
        f"About the role: {job.about_the_role}" if job.about_the_role else "",
        f"Key responsibilities: {job.key_responsibilities}"
        if job.key_responsibilities
        else "",
        f"Requirements: {job.requirements}" if job.requirements else "",
        f"Technical competencies: {job.technical_competencies}"
        if job.technical_competencies
        else "",
    ]
    job_context = "\n\n".join(p for p in job_context_parts if p)

    ai_service = AnthropicCVExtractionService()
    try:
        result = await ai_service.score_interview_transcript(
            interview_brief=job.interview_brief or "",
            transcript=interview.transcript,
            job_context=job_context,
        )
    finally:
        await ai_service._client.close()

    rationale_parts = [result.summary]
    if result.strengths:
        rationale_parts.append(
            "Strengths:\n" + "\n".join(f"- {s}" for s in result.strengths)
        )
    if result.weaknesses:
        rationale_parts.append(
            "Weaknesses:\n" + "\n".join(f"- {w}" for w in result.weaknesses)
        )
    if result.missing_evidence:
        rationale_parts.append(
            "Not covered in this interview:\n"
            + "\n".join(f"- {m}" for m in result.missing_evidence)
        )
    if result.contradictions:
        rationale_parts.append(
            "Contradictions:\n" + "\n".join(f"- {c}" for c in result.contradictions)
        )

    await repo.update(
        interview.id,
        {
            "ai_score": result.score,
            "ai_rationale": "\n\n".join(p for p in rationale_parts if p),
            "ai_scored_at": datetime.now(UTC),
        },
    )
    await db.commit()
    print(f"  OK {interview_id}: rescored -> {result.score}/100")


async def main(interview_ids: list[str]) -> None:
    engine = create_async_engine(
        settings.database_url, pool_pre_ping=True, poolclass=NullPool
    )
    sessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionLocal() as db:
        repo = InterviewRepository(db)
        for raw_id in interview_ids:
            await rescore_one(db, repo, uuid.UUID(raw_id))

    await engine.dispose()


if __name__ == "__main__":
    ids = sys.argv[1:]
    if not ids:
        print("Usage: python scripts/rescore_interview.py <interview_id> [more ids...]")
        sys.exit(1)
    asyncio.run(main(ids))
