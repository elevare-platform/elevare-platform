"""A job's follow-up mode: what the AI may do after an answer in its strict interview
(docs/08_DECISIONS.md, item 40).

Stored in ``job_interview_settings``, one row per job. A job without a row is STANDARD, which is
how every job behaved before the choice existed. The table was added by migration p22_0034, so a
read tolerates it not being there yet (the seconds of a deploy before the migration has run).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schema_guard import tolerate_missing
from app.modules.interviews.enums import FollowUpMode, follow_up_mode_of
from app.modules.interviews.models import JobInterviewSettings


async def load_follow_up_mode(db: AsyncSession, job_id: uuid.UUID) -> FollowUpMode:
    """The job's follow-up mode; STANDARD when it has none (or the table is not there yet)."""

    async def read() -> FollowUpMode:
        result = await db.execute(
            select(JobInterviewSettings.follow_up_mode).where(JobInterviewSettings.job_id == job_id)
        )
        return follow_up_mode_of(result.scalar_one_or_none())

    return await tolerate_missing(db, read, FollowUpMode.STANDARD)


async def save_follow_up_mode(db: AsyncSession, job_id: uuid.UUID, mode: FollowUpMode) -> None:
    """Set the job's mode (flushed, not committed: the caller commits with the rest)."""
    existing = (
        await db.execute(select(JobInterviewSettings).where(JobInterviewSettings.job_id == job_id))
    ).scalar_one_or_none()
    if existing is None:
        db.add(JobInterviewSettings(job_id=job_id, follow_up_mode=mode.value))
    else:
        existing.follow_up_mode = mode.value
    await db.flush()
