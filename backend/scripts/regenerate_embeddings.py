"""Regenerate job/candidate/talent-pool embeddings with the updated text builder.

Job embeddings now include title + required_skills; candidate and
talent-pool embeddings now include skills. Run this locally first to check
results (via the AI Talent Match UI) before running the same against
production.

Calls the embedding-generation functions directly (not via Celery `.delay()`)
so it runs synchronously with no worker/broker needed — just this process
talking to the DB and OpenAI.

Usage (from inside the api container, or locally with the right DATABASE_URL):
    python scripts/regenerate_embeddings.py                        # dry run — counts only
    python scripts/regenerate_embeddings.py --apply                 # regenerate everything
    python scripts/regenerate_embeddings.py --apply --jobs-only
    python scripts/regenerate_embeddings.py --apply --candidates-only
    python scripts/regenerate_embeddings.py --apply --talent-pool-only
    python scripts/regenerate_embeddings.py --apply --limit 5        # spot-check a handful first
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

import app.core.model_registry  # noqa: F401 — ensures all mappers are registered before any DB use
from app.core.database import AsyncSessionLocal
from app.modules.candidates.models import CandidateProfile
from app.modules.jobs.enums import JobStatus
from app.modules.jobs.models import Job
from app.modules.talent_pool.models import TalentPoolProfiles


def _flag(name: str) -> bool:
    return name in sys.argv


def _int_flag(name: str) -> int | None:
    if name not in sys.argv:
        return None
    return int(sys.argv[sys.argv.index(name) + 1])


async def run(apply: bool, categories: set[str], limit: int | None) -> None:
    async with AsyncSessionLocal() as db:
        job_ids: list = []
        candidate_ids: list = []
        tp_ids: list = []

        if "jobs" in categories:
            stmt = select(Job.id).where(Job.status == JobStatus.ACTIVE.value)
            if limit:
                stmt = stmt.limit(limit)
            job_ids = [r[0] for r in (await db.execute(stmt)).all()]

        if "candidates" in categories:
            stmt = select(CandidateProfile.id)
            if limit:
                stmt = stmt.limit(limit)
            candidate_ids = [r[0] for r in (await db.execute(stmt)).all()]

        if "talent_pool" in categories:
            stmt = select(TalentPoolProfiles.id)
            if limit:
                stmt = stmt.limit(limit)
            tp_ids = [r[0] for r in (await db.execute(stmt)).all()]

    print(
        f"Jobs: {len(job_ids)}  Candidates: {len(candidate_ids)}  "
        f"Talent pool: {len(tp_ids)}"
    )

    if not apply:
        print("\nDry run — re-run with --apply to actually regenerate.")
        return

    # Clear stored hashes first so the hash-check inside each generation
    # function can't decide "unchanged" and skip — guarantees regeneration
    # regardless of hash edge cases, same as the production reindex endpoint.
    async with AsyncSessionLocal() as db:
        if job_ids:
            await db.execute(
                update(Job)
                .where(Job.id.in_(job_ids))
                .values(embedding_source_hash=None)
            )
        if candidate_ids:
            await db.execute(
                update(CandidateProfile)
                .where(CandidateProfile.id.in_(candidate_ids))
                .values(embedding_source_hash=None)
            )
        if tp_ids:
            await db.execute(
                update(TalentPoolProfiles)
                .where(TalentPoolProfiles.id.in_(tp_ids))
                .values(embedding_source_hash=None)
            )
        await db.commit()

    from app.modules.ai.tasks import (
        _generate_candidate_embedding_async,
        _generate_job_embedding_async,
        _generate_talent_pool_embedding_async,
    )

    failures = []

    for i, jid in enumerate(job_ids, 1):
        print(f"[job {i}/{len(job_ids)}] {jid}")
        try:
            await _generate_job_embedding_async(str(jid))
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append(("job", jid, str(e)))

    for i, cid in enumerate(candidate_ids, 1):
        print(f"[candidate {i}/{len(candidate_ids)}] {cid}")
        try:
            await _generate_candidate_embedding_async(str(cid))
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append(("candidate", cid, str(e)))

    for i, tid in enumerate(tp_ids, 1):
        print(f"[talent_pool {i}/{len(tp_ids)}] {tid}")
        try:
            await _generate_talent_pool_embedding_async(str(tid))
        except Exception as e:
            print(f"  FAILED: {e}")
            failures.append(("talent_pool", tid, str(e)))

    print(f"\nDone. {len(failures)} failure(s).")
    for kind, _id, err in failures:
        print(f"  {kind} {_id}: {err}")


if __name__ == "__main__":
    apply = _flag("--apply")
    limit = _int_flag("--limit")

    only_flags = {
        "jobs": _flag("--jobs-only"),
        "candidates": _flag("--candidates-only"),
        "talent_pool": _flag("--talent-pool-only"),
    }
    if any(only_flags.values()):
        categories = {k for k, v in only_flags.items() if v}
    else:
        categories = {"jobs", "candidates", "talent_pool"}

    if apply:
        confirm = input(
            f"This will regenerate embeddings for {categories} "
            f"{f'(limit {limit} each)' if limit else '(all rows)'}. "
            "Costs OpenAI API calls. Type 'yes' to continue: "
        )
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    asyncio.run(run(apply=apply, categories=categories, limit=limit))
