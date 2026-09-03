"""One-off campaign: email everyone whose account is still unverified.

Idempotent by design: a user is skipped if they already have a live
(unused, unexpired) verification token. That means they were already
reminded recently and haven't clicked yet. So the exact same command can be
re-run safely at any time, for example in batches to stay under an email
provider's rate limit, without re-emailing anyone who was just sent one.
``--limit`` is a batch-size cap, not an offset or page number. It does not
need to change between runs, since each run naturally picks up wherever the
live-token set left off. Do not add a ``--skip``/offset flag here instead:
the recipient pool shrinks as people verify, so an offset would silently
skip people who were never emailed once the earlier ones start verifying.

Each recipient gets a *fresh* verification token (creating one invalidates
their old unused tokens, so only the newest link works) and an email that:

- for EMPLOYER accounts, offers two doors: "confirm as an employer" or
  "switch me to a job seeker account". Both verify the email, and the second
  also flips the role. This is the recovery path for people who clicked
  "Hire Talent" on the homepage when they meant "Find a Role".
- for CANDIDATE accounts, is a plain verification nudge, with the reverse
  switch link as a secondary option.

The role switch is handled server-side in ``AuthService.verify_email`` and is
only honoured while the account is still PENDING_VERIFICATION.

Tokens expire after ``settings.email_verification_token_expiry`` hours (24 by
default), so send this when you're ready for people to act on it.

Run from inside the API container, ALWAYS dry-run first. Use ``-m`` (module
mode, not a bare file path). The working directory there is ``/app``, and
``-m`` puts that on ``sys.path`` so ``app.core.email`` etc. resolve. Running
the .py file directly only puts ``scripts/`` on the path and fails with
``ModuleNotFoundError: No module named 'app'``:

    python -m scripts.send_verification_reminders --dry-run
    python -m scripts.send_verification_reminders --role EMPLOYER --limit 3
    python -m scripts.send_verification_reminders
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.core.model_registry  # noqa: F401, ensures all mappers are registered before any DB use
from app.core.config import settings
from app.core.email import get_email_service
from app.modules.auth.models import EmailVerificationToken
from app.modules.auth.service import AuthService
from app.modules.users.enums import AccountStatus, UserRole
from app.modules.users.models import User

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("reminders")

# Resend's default rate limit is 2 requests per second. Stay comfortably under it.
SEND_INTERVAL_SECONDS = 0.6


async def load_recipients(db, role: str | None, limit: int | None) -> list[User]:
    """Fetch unverified, non-admin accounts with no live reminder outstanding, oldest first.

    "No live reminder outstanding" (no unused, unexpired EmailVerificationToken)
    is what makes re-running this script safe: someone already reminded in an
    earlier run is excluded until their token is used or expires, so the same
    command can be split across multiple runs without duplicate sends.
    """
    has_live_token = (
        select(EmailVerificationToken.id)
        .where(
            EmailVerificationToken.user_id == User.id,
            EmailVerificationToken.is_used.is_(False),
            EmailVerificationToken.expires_at > datetime.now(UTC),
        )
        .exists()
    )
    stmt = (
        select(User)
        .where(
            User.account_status == AccountStatus.PENDING_VERIFICATION.value,
            User.email_verified.is_(False),
            User.role != UserRole.ADMIN.value,
            ~has_live_token,
        )
        .order_by(User.created_at)
    )
    if role:
        stmt = stmt.where(User.role == role)
    if limit:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def main() -> None:
    """Send (or preview) one reminder per unverified account."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--role",
        choices=[UserRole.EMPLOYER.value, UserRole.CANDIDATE.value],
        help="only email this role (default: both)",
    )
    parser.add_argument("--limit", type=int, help="cap how many are emailed")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list who would be emailed without creating tokens or sending",
    )
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            recipients = await load_recipients(db, args.role, args.limit)

            logger.info("%d unverified account(s) match.", len(recipients))
            if not recipients:
                return

            if args.dry_run:
                logger.info("\nDRY RUN, nothing sent, no tokens created:\n")
                for user in recipients:
                    logger.info(
                        "  %-38s %-10s created %s",
                        user.email,
                        user.role,
                        user.created_at.date() if user.created_at else "?",
                    )
                logger.info(
                    "\nRe-run without --dry-run to send. Links expire after %d hours.",
                    settings.email_verification_token_expiry,
                )
                return

            service = get_email_service()
            auth = AuthService(db)
            sent = 0
            failed = []

            for user in recipients:
                try:
                    token = await auth.create_verification_token(user.id)
                    await service.send_verification_reminder(
                        email=user.email,
                        first_name=user.first_name or "",
                        verification_token=token,
                        role=user.role,
                    )
                    sent += 1
                    logger.info("  sent -> %s (%s)", user.email, user.role)
                except Exception as exc:
                    # One bad address shouldn't abort the rest of the batch.
                    failed.append((user.email, str(exc)))
                    logger.error("  FAILED -> %s: %s", user.email, exc)

                await asyncio.sleep(SEND_INTERVAL_SECONDS)

            logger.info("\nDone. %d sent, %d failed.", sent, len(failed))
            for email, err in failed:
                logger.info("  failed: %s: %s", email, err)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
