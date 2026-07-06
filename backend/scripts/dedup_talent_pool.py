"""One-time deduplication script for talent_pool_profiles.

Finds profiles sharing the same (cv_text_hash, sourced_for_job_id) combination,
keeps the oldest one (lowest created_at), and deletes the duplicates.

Run with:
    python scripts/dedup_talent_pool.py           # dry run — shows what would be deleted
    python scripts/dedup_talent_pool.py --apply   # actually deletes duplicates
"""
import asyncio
import sys
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, "/app")

from app.core.config import settings
from app.modules.ai.models import ParsedCVSubmission
from app.modules.talent_pool.models import TalentPoolProfiles


async def run(apply: bool) -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as db:
        # Load all profiles that have a parsed submission
        result = await db.execute(
            select(TalentPoolProfiles, ParsedCVSubmission.cv_text_hash)
            .join(
                ParsedCVSubmission,
                TalentPoolProfiles.parsed_submission_id == ParsedCVSubmission.id,
            )
            .order_by(TalentPoolProfiles.created_at.asc())
        )
        rows = result.all()

    # Group by (cv_text_hash, sourced_for_job_id)
    groups: dict[tuple, list] = defaultdict(list)
    for profile, cv_hash in rows:
        key = (cv_hash, str(profile.sourced_for_job_id))
        groups[key].append(profile)

    duplicates = {k: v for k, v in groups.items() if len(v) > 1}

    if not duplicates:
        print("No duplicates found. Nothing to do.")
        await engine.dispose()
        return

    total_to_delete = sum(len(v) - 1 for v in duplicates.values())
    print(f"Found {len(duplicates)} duplicate group(s) — {total_to_delete} profile(s) to remove.\n")

    async with Session() as db:
        for (cv_hash, job_id), profiles in duplicates.items():
            keep = profiles[0]  # oldest — already sorted by created_at asc
            to_delete = profiles[1:]

            print(f"  Hash: {cv_hash[:16]}…  Job: {job_id}")
            print(f"    Keep   : {keep.id}  (created {keep.created_at})")
            for p in to_delete:
                print(f"    Delete : {p.id}  (created {p.created_at})")
                if apply:
                    await db.delete(p)

        if apply:
            await db.commit()
            print(f"\nDone — deleted {total_to_delete} duplicate profile(s).")
        else:
            print(f"\nDry run complete. Re-run with --apply to delete {total_to_delete} profile(s).")

    await engine.dispose()


if __name__ == "__main__":
    apply = "--apply" in sys.argv
    if apply:
        confirm = input("This will permanently delete duplicate profiles. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            sys.exit(0)
    asyncio.run(run(apply=apply))
