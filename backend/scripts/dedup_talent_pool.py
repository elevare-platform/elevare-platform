"""Merge talent pool profiles that are the same CV in the same person's pool.

Nothing is deleted. For each set of duplicates one profile is kept, everything that points at
the others (introduction requests, saved candidates, interview list entries, interviews, role and
match notifications, scoring costs) is moved onto it, and the others are ARCHIVED with a note
saying which profile they were merged into.

What counts as a duplicate (the same rule the upload now uses, talent_pool/dedupe.py):
  * the same CV content, in the pool of the SAME person (`added_by`): never across employers,
    whose private profiles must stay private;
  * for the same job, or both with no job;
  * and a profile with no job that sits next to exactly one profile for a job, for the same CV
    (it is merged into the job's one). Two different jobs are kept apart on purpose.
Sets with the old empty-text hash are skipped: every CV with no readable text used to get the
same hash, so those are unrelated people, not copies.

A set is left for a person to look at (and reported) when merging it could lose something:
two of its profiles are promoted to an application, two belong to a self-registered
candidate, or two have an interview for the same job.

It reports by default and CHANGES NOTHING. A "dry run" (the default) runs the real statements
for each set and then rolls them back, so the counts it prints are exactly what a real run does.

Run it from inside the API container, in module mode (the working directory there is /app):

    # 1. see what would happen (changes nothing)
    docker compose -f docker-compose.prod.yml exec -T api python -m scripts.dedup_talent_pool

    # 2. do it, for a few sets first
    docker compose -f docker-compose.prod.yml exec -T api python -m scripts.dedup_talent_pool --apply --yes --limit 5

    # 3. then all of them
    docker compose -f docker-compose.prod.yml exec -T api python -m scripts.dedup_talent_pool --apply --yes

Take a database backup first (see docs/postgres-backup-restore.md). Archived profiles can be
brought back by setting their status to 'new' again; moved rows keep their own ids.
"""

import argparse
import asyncio
import hashlib
import hmac
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Tables with a talent_pool_profile_id that moves to the kept profile as it is.
MOVE_AS_IS = ("introduction_requests", "match_notifications", "fit_scoring_costs")


def empty_text_hash() -> str:
    """The hash older code gave to EVERY CV with no extractable text."""
    return hmac.new(settings.hmac_secret.encode(), b"", hashlib.sha256).hexdigest()


@dataclass
class Merge:
    """Move `losers` into `keeper`. `reason` is why they are the same CV."""

    keeper: dict
    losers: list[dict]
    reason: str
    skip: str | None = None  # set when it must not be merged automatically
    moved: Counter = field(default_factory=Counter)


def _rank(profile: dict, children: Counter) -> tuple:
    """Which profile to keep: the one bound to an application or a self-registered candidate
    (those cannot move), then one that has a score, then the one with the most work attached,
    then the oldest."""
    return (
        profile["promoted_application_id"] is not None,
        profile["candidate_profile_id"] is not None,
        profile["ai_score"] is not None,
        children[profile["id"]],
        -profile["created_at"].timestamp(),
        str(profile["id"]),
    )


def _bound(profile: dict) -> bool:
    """Tied to an application or a self-registered candidate: it cannot be merged away."""
    return profile["promoted_application_id"] is not None or profile["candidate_profile_id"] is not None


def _group_merge(profiles: list[dict], children: Counter, reason: str) -> Merge:
    ordered = sorted(profiles, key=lambda p: _rank(p, children), reverse=True)
    keeper, losers = ordered[0], ordered[1:]
    skip = None
    if sum(p["promoted_application_id"] is not None for p in ordered) > 1:
        skip = "more than one is promoted to an application"
    elif sum(p["candidate_profile_id"] is not None for p in ordered) > 1:
        skip = "more than one belongs to a self-registered candidate"
    elif any(_bound(loser) for loser in losers):
        skip = "a profile bound to an application or a candidate would be merged away"
    return Merge(keeper, losers, reason, skip)


def plan_merges(profiles: list[dict], children: Counter, ignore_hash: str) -> list[Merge]:
    """Group profiles into the merges described at the top of this file. Pure: no database."""
    by_person: dict[tuple, list[dict]] = defaultdict(list)
    for profile in profiles:
        if profile["cv_text_hash"] and profile["cv_text_hash"] != ignore_hash:
            by_person[(profile["cv_text_hash"], profile["added_by"])].append(profile)

    merges: list[Merge] = []
    for same_cv in by_person.values():
        by_job: dict = defaultdict(list)
        for profile in same_cv:
            by_job[profile["sourced_for_job_id"]].append(profile)

        survivors: dict = {}
        for job_id, group in by_job.items():
            if len(group) > 1:
                merge = _group_merge(group, children, "the same CV for the same job" if job_id else "the same CV with no job")
                merges.append(merge)
                survivors[job_id] = merge.keeper
            else:
                survivors[job_id] = group[0]

        without_job = survivors.get(None)
        with_job = [p for j, p in survivors.items() if j is not None]
        if without_job is not None and len(with_job) == 1:
            # The profile for the job is the one to keep, whatever its rank.
            merges.append(
                Merge(
                    with_job[0],
                    [without_job],
                    "a copy with no job beside the same CV for a job",
                    skip="the copy with no job is bound to an application or a candidate"
                    if _bound(without_job)
                    else None,
                )
            )
    return merges


async def load(session: AsyncSession) -> tuple[list[dict], Counter]:
    rows = (
        await session.execute(
            text(
                """
                SELECT p.id, p.added_by, p.sourced_for_job_id, p.status, p.created_at,
                       p.candidate_profile_id, p.promoted_application_id, p.ai_score,
                       s.cv_text_hash
                FROM talent_pool_profiles p
                JOIN parsed_cv_submissions s ON s.id = p.parsed_submission_id
                WHERE p.status <> 'archived' AND s.cv_text_hash IS NOT NULL
                """
            )
        )
    ).mappings().all()
    children: Counter = Counter()
    for table in (*MOVE_AS_IS, "saved_candidates", "interview_list_entries", "interviews", "role_notifications"):
        counted = await session.execute(
            text(f"SELECT talent_pool_profile_id AS id, count(*) AS n FROM {table} GROUP BY 1")  # noqa: S608
        )
        for row in counted.mappings():
            children[row["id"]] += row["n"]
    return [dict(r) for r in rows], children


async def interview_conflict(session: AsyncSession, keeper_id, loser_id) -> bool:
    """Both profiles already have an interview for the same job (the pair must be unique)."""
    found = await session.execute(
        text(
            """
            SELECT 1 FROM interviews a JOIN interviews b ON a.job_id = b.job_id
            WHERE a.talent_pool_profile_id = :keeper AND b.talent_pool_profile_id = :loser LIMIT 1
            """
        ),
        {"keeper": keeper_id, "loser": loser_id},
    )
    return found.first() is not None


async def _move(session: AsyncSession, sql: str, keeper_id, loser_id) -> int:
    result = await session.execute(text(sql), {"keeper": keeper_id, "loser": loser_id})
    return result.rowcount or 0


async def merge_one(session: AsyncSession, merge: Merge) -> None:
    """Run one merge's statements. The caller commits or rolls back."""
    keeper_id = merge.keeper["id"]
    for loser in merge.losers:
        loser_id = loser["id"]
        for table in MOVE_AS_IS:
            merge.moved[table] += await _move(
                session,
                f"UPDATE {table} SET talent_pool_profile_id = :keeper WHERE talent_pool_profile_id = :loser",  # noqa: S608
                keeper_id,
                loser_id,
            )
        # Interviews: the pair (job, profile) is unique; a conflict was ruled out before this.
        merge.moved["interviews"] += await _move(
            session,
            "UPDATE interviews SET talent_pool_profile_id = :keeper WHERE talent_pool_profile_id = :loser",
            keeper_id,
            loser_id,
        )
        # Where the kept profile already has the same row, the loser's is the same fact twice.
        for table, same in (
            ("saved_candidates", "k.employer_id = s.employer_id"),
            ("interview_list_entries", "k.employer_id = s.employer_id AND k.job_id IS NOT DISTINCT FROM s.job_id"),
            (
                "role_notifications",
                "k.employer_id = s.employer_id AND k.job_id IS NOT DISTINCT FROM s.job_id",
            ),
        ):
            merge.moved[f"{table} (already on the kept profile, dropped)"] += await _move(
                session,
                f"""
                DELETE FROM {table} s WHERE s.talent_pool_profile_id = :loser AND EXISTS (
                  SELECT 1 FROM {table} k WHERE k.talent_pool_profile_id = :keeper AND {same})
                """,  # noqa: S608
                keeper_id,
                loser_id,
            )
            merge.moved[table] += await _move(
                session,
                f"UPDATE {table} SET talent_pool_profile_id = :keeper WHERE talent_pool_profile_id = :loser",  # noqa: S608
                keeper_id,
                loser_id,
            )
        # The kept profile takes the job if it has none and the copy did.
        if merge.keeper["sourced_for_job_id"] is None and loser["sourced_for_job_id"] is not None:
            await session.execute(
                text("UPDATE talent_pool_profiles SET sourced_for_job_id = :job WHERE id = :keeper"),
                {"job": loser["sourced_for_job_id"], "keeper": keeper_id},
            )
        await session.execute(
            text(
                """
                UPDATE talent_pool_profiles
                SET status = 'archived',
                    source_note = left(coalesce(source_note, '') || ' [merged into ' || :keeper || ']', 1000)
                WHERE id = :loser
                """
            ),
            {"keeper": str(keeper_id), "loser": loser_id},
        )
        merge.moved["profiles archived"] += 1


async def run(apply: bool, limit: int | None) -> int:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        profiles, children = await load(session)
    merges = plan_merges(profiles, children, empty_text_hash())
    skipped_empty = sum(1 for p in profiles if p["cv_text_hash"] == empty_text_hash())

    todo = [m for m in merges if not m.skip]
    manual = [m for m in merges if m.skip]
    if limit:
        todo = todo[:limit]

    print(f"{'APPLYING' if apply else 'DRY RUN (changes nothing)'}")
    print(f"{len(profiles)} active profiles with a parsed CV looked at.")
    print(f"{len(merges)} set(s) of duplicates found: {len(todo)} to merge now, {len(manual)} for a person to look at.")
    if skipped_empty:
        print(f"{skipped_empty} profile(s) left alone: they share the old empty-text hash (unrelated CVs).")

    totals: Counter = Counter()
    for merge in todo:
        async with Session() as session:
            if any([await interview_conflict(session, merge.keeper["id"], loser["id"]) for loser in merge.losers]):
                merge.skip = "both already have an interview for the same job"
                manual.append(merge)
                continue
            await merge_one(session, merge)
            if apply:
                await session.commit()
            else:
                await session.rollback()
        totals.update(merge.moved)
        loser_ids = ", ".join(str(loser["id"]) for loser in merge.losers)
        print(f"  keep {merge.keeper['id']}  merge {loser_ids}  ({merge.reason})")

    if manual:
        print("\nFor a person to look at (nothing was changed for these):")
        for merge in manual:
            ids = ", ".join(str(p["id"]) for p in [merge.keeper, *merge.losers])
            print(f"  {ids}: {merge.skip}")

    print("\nTotals" + (" (what a real run would do):" if not apply else ":"))
    for key, value in sorted(totals.items()):
        print(f"  {key}: {value}")
    if not apply:
        print("\nNothing was changed. To do it: add --apply --yes (try --limit 5 first).")
    await engine.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--apply", action="store_true", help="really merge (default: report only)")
    parser.add_argument("--yes", action="store_true", help="confirm --apply")
    parser.add_argument("--limit", type=int, help="merge at most this many sets")
    args = parser.parse_args(argv)
    if args.apply and not args.yes:
        print("--apply changes data. Add --yes to confirm (and take a backup first).")
        return 2
    return asyncio.run(run(args.apply, args.limit))


if __name__ == "__main__":
    sys.exit(main())
