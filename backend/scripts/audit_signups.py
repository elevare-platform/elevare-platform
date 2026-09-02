"""Read-only report on stalled sign-ups and mis-picked roles.

Answers two questions before any email goes out:

1. Who never clicked their verification link (account_status is still
   PENDING_VERIFICATION), split by role — these are the accounts
   ``send_verification_reminders.py`` targets.
2. Which EMPLOYER accounts have no company attached (no organization, or an
   organization with no company_name). Job seekers who clicked "Hire Talent"
   on the homepage by mistake land here, so this is the best proxy we have
   for the size of the wrong-role problem.

Run from inside the API container:
    python scripts/audit_signups.py
    python scripts/audit_signups.py --csv /tmp/signups.csv
"""

import argparse
import asyncio
import csv
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import Organization, User


async def collect(db) -> list[dict]:
    """Return one row per non-admin user with the fields this report cares about."""
    stmt = (
        select(User, Organization)
        .outerjoin(Organization, User.organization_id == Organization.id)
        .where(User.role != UserRole.ADMIN.value)
        .order_by(User.created_at)
    )
    result = await db.execute(stmt)

    now = datetime.now(UTC)
    rows = []
    for user, org in result.all():
        created = user.created_at
        age_days = (now - created).days if created else None
        rows.append(
            {
                "id": str(user.id),
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "role": user.role,
                "account_status": user.account_status,
                "email_verified": user.email_verified,
                "company_name": (org.company_name if org else None) or "",
                "has_company": bool(org and org.company_name),
                "created_at": created.isoformat() if created else "",
                "age_days": age_days,
            }
        )
    return rows


def report(rows: list[dict]) -> None:
    """Print the human-readable summary."""
    pending = [r for r in rows if r["account_status"] == AccountStatus.PENDING_VERIFICATION.value]
    employers = [r for r in rows if r["role"] == UserRole.EMPLOYER.value]
    candidates = [r for r in rows if r["role"] == UserRole.CANDIDATE.value]

    print(f"\n{'=' * 68}")
    print(f"  Sign-up audit — {len(rows)} non-admin accounts")
    print(f"{'=' * 68}\n")

    print(f"  Employers                     {len(employers):>4}")
    print(f"    ...with a company name      {len([r for r in employers if r['has_company']]):>4}")
    print(f"    ...WITHOUT a company name   {len([r for r in employers if not r['has_company']]):>4}   <- likely wrong-role signups")
    print(f"  Candidates                    {len(candidates):>4}\n")

    pending_employers = [r for r in pending if r["role"] == UserRole.EMPLOYER.value]
    pending_candidates = [r for r in pending if r["role"] == UserRole.CANDIDATE.value]
    print(f"  Never verified their email    {len(pending):>4}")
    print(f"    as EMPLOYER                 {len(pending_employers):>4}")
    print(f"    as CANDIDATE                {len(pending_candidates):>4}\n")

    for label, group in (
        ("UNVERIFIED EMPLOYERS", pending_employers),
        ("UNVERIFIED CANDIDATES", pending_candidates),
    ):
        if not group:
            continue
        print(f"  {label}")
        print(f"  {'-' * 66}")
        for r in group:
            company = r["company_name"] or "(no company)"
            print(f"    {r['email']:<38} {company:<20} {r['age_days']}d old")
        print()


async def main() -> None:
    """Collect the rows, print the report, and optionally write a CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", help="also write every row to this CSV path")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    try:
        async with SessionLocal() as db:
            rows = await collect(db)
    finally:
        await engine.dispose()

    report(rows)

    if args.csv:
        with open(args.csv, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"  Wrote {len(rows)} rows to {args.csv}\n")


if __name__ == "__main__":
    asyncio.run(main())
