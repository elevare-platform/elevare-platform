"""One-off backfill: fix accounts left half-migrated by the role-switch bug.

Background: the self-service role correction added to email verification
(``AuthService.verify_email(token, switch_role=...)``) originally only set
``User.role`` and never provisioned the corresponding CandidateProfile /
Organization row a normal registration always creates. Anyone who used a
"switch me to a job seeker/employer" link before that was fixed is left with
a role string that doesn't match their actual DB state, for example
role=CANDIDATE with no CandidateProfile row, which 500s on every candidate-only endpoint
(``has-applied``, ``apply``, ``my applications``, ...) via
``get_candidate()`` returning ``None``.

This script finds and fixes exactly that mismatch, then emails each person
to say their account is fixed and they can log back in:

- role=CANDIDATE with no CandidateProfile row -> creates one (and enrolls
  them in the talent pool), same as ``UserRepository.provision_candidate_profile``.
- role=EMPLOYER with no organization_id -> creates a fresh Organization
  they own, same as ``UserRepository.provision_organization``.

Safe to re-run: only ever acts on rows currently missing the profile/org, so
a second run finds nothing left to do (and sends no duplicate emails).

The same detection queries back the periodic ``heal_role_switch_profiles_task``
(``app/modules/users/tasks.py``, runs every 6 hours). This script is for
running the fix immediately instead of waiting for the next scheduled pass,
for example right after discovering the bug.

Run from inside the API container, ALWAYS dry-run first. Use ``-m`` (module
mode, not a bare file path). See audit_signups.py's docstring for why:

    python -m scripts.backfill_role_switch_profiles --dry-run
    python -m scripts.backfill_role_switch_profiles
"""

import argparse
import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.core.model_registry  # noqa: F401, ensures all mappers are registered before any DB use
from app.core.config import settings
from app.core.email import get_email_service
from app.modules.users.repository import UserRepository

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill")


async def main() -> None:
    """Find and fix (or preview) half-migrated accounts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list who would be fixed without writing anything",
    )
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            repo = UserRepository(db)
            broken_candidates = await repo.list_candidates_missing_profile()
            broken_employers = await repo.list_employers_missing_organization()

            logger.info(
                "%d role=CANDIDATE account(s) missing a CandidateProfile.",
                len(broken_candidates),
            )
            for u in broken_candidates:
                logger.info("  %-38s created %s", u.email, u.created_at.date())

            logger.info(
                "\n%d role=EMPLOYER account(s) missing an Organization.",
                len(broken_employers),
            )
            for u in broken_employers:
                logger.info("  %-38s created %s", u.email, u.created_at.date())

            if not broken_candidates and not broken_employers:
                logger.info("\nNothing to fix.")
                return

            if args.dry_run:
                logger.info("\nDRY RUN, nothing written. Re-run without --dry-run to fix.")
                return

            # Provision everything and commit first. Only email once the fix
            # is durably saved, so a failed commit can never leave someone
            # told "you're fixed" when the DB write didn't actually happen.
            for u in broken_candidates:
                await repo.provision_candidate_profile(u)
            for u in broken_employers:
                await repo.provision_organization(u)
            await db.commit()

            email_service = get_email_service()
            for u in broken_candidates:
                await email_service.send_role_switch_corrected(
                    email=u.email, first_name=u.first_name or "", role="CANDIDATE"
                )
                logger.info(
                    "  fixed -> %s (candidate profile created, notified)", u.email
                )
            for u in broken_employers:
                await email_service.send_role_switch_corrected(
                    email=u.email, first_name=u.first_name or "", role="EMPLOYER"
                )
                logger.info(
                    "  fixed -> %s (organization created, notified)", u.email
                )

            logger.info(
                "\nDone. %d candidate profile(s), %d organization(s) created and notified.",
                len(broken_candidates),
                len(broken_employers),
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
