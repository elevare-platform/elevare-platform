"""Celery tasks for the users module: account setup reminders and the
role-switch self-heal backstop.

Mirrors billing/tasks.py's reconcile_pending_payments_task shape: one
periodic sweep, its own engine, disposed in a finally block.
"""

import asyncio
import logging
from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.celery_app import celery
from app.core.config import settings
from app.core.email import get_email_service
from app.modules.auth.service import AuthService
from app.modules.notifications.repository import NotificationRepository
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)

# How long an account sits in a stuck state before the first nudge, so
# nobody gets emailed minutes after signing up while still actively
# filling things in.
REMINDER_GRACE_PERIOD = timedelta(hours=24)


@celery.task(time_limit=60 * 5, soft_time_limit=60 * 4)
def heal_role_switch_profiles_task():
    """Celery Beat task. Finds and fixes accounts left half-migrated by a role switch.

    Should find nothing in steady state: every path that changes a user's
    role now provisions the matching CandidateProfile/Organization in the
    same transaction (see UserRepository.provision_candidate_profile /
    provision_organization). This exists as a low-frequency safety net for
    that invariant. The class of bug that motivated it (verify-email's role
    switch flipping the role string without provisioning the profile) is
    already fixed at the source, so this should rarely if ever find work.
    If it does, it's the only thing standing between that gap and a user
    hitting a 500 on every candidate/employer-only endpoint until someone
    notices.
    """
    asyncio.run(_run_heal_async())


async def _run_heal_async() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            repo = UserRepository(db)
            broken_candidates = await repo.list_candidates_missing_profile()
            broken_employers = await repo.list_employers_missing_organization()

            if not broken_candidates and not broken_employers:
                return

            logger.warning(
                "heal_role_switch_profiles_task: found %d half-migrated "
                "candidate(s) and %d half-migrated employer(s), fixing.",
                len(broken_candidates),
                len(broken_employers),
            )

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
            for u in broken_employers:
                await email_service.send_role_switch_corrected(
                    email=u.email, first_name=u.first_name or "", role="EMPLOYER"
                )

            logger.info(
                "heal_role_switch_profiles_task: fixed and notified %d account(s).",
                len(broken_candidates) + len(broken_employers),
            )
    finally:
        await engine.dispose()


@celery.task(time_limit=60 * 10, soft_time_limit=60 * 9)
def send_account_setup_reminders_task():
    """Celery Beat task. Reminds accounts stuck unverified, un-onboarded, or un-KYC'd.

    Runs once a day. Three checks, each sent at most once ever per account:

    - Candidates and employers who never verified their email.
    - Employer owners who verified but never completed their company
      profile.
    - Employer owners who onboarded but never submitted KYC documents.

    An employer stuck on both onboarding and KYC only ever gets the
    onboarding email, since UserRepository.list_employers_missing_kyc only
    matches accounts where onboarding is already complete.

    "Already reminded" is tracked via a Notification row of the matching
    type, created only after the email send succeeds, so a failed send
    doesn't get marked as done and is retried on the next run.
    """
    asyncio.run(_run_reminders_async())


async def _run_reminders_async() -> None:
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with SessionLocal() as db:
            repo = UserRepository(db)
            unverified = await repo.list_unverified_users(REMINDER_GRACE_PERIOD)
            missing_onboarding = await repo.list_employers_missing_onboarding(
                REMINDER_GRACE_PERIOD
            )
            missing_kyc = await repo.list_employers_missing_kyc(REMINDER_GRACE_PERIOD)

            if not unverified and not missing_onboarding and not missing_kyc:
                return

            logger.info(
                "send_account_setup_reminders_task: %d unverified, %d missing "
                "onboarding, %d missing KYC.",
                len(unverified),
                len(missing_onboarding),
                len(missing_kyc),
            )

            email_service = get_email_service()
            notifications = NotificationRepository(db)
            auth = AuthService(db)
            sent = 0

            for u in unverified:
                try:
                    token = await auth.create_verification_token(u.id)
                    await email_service.send_verification_reminder(
                        email=u.email,
                        first_name=u.first_name or "",
                        verification_token=token,
                        role=u.role,
                    )
                    await notifications.create(
                        recipient_id=u.id,
                        type="VERIFICATION_REMINDER",
                        title="Verify your email",
                        body="Verify your email to activate your Elevare account.",
                    )
                    await db.commit()
                    sent += 1
                except Exception:
                    logger.exception(
                        "send_account_setup_reminders_task: failed to remind %s "
                        "(unverified)",
                        u.email,
                    )

            for u in missing_onboarding:
                try:
                    await email_service.send_onboarding_reminder(
                        email=u.email, first_name=u.first_name or ""
                    )
                    await notifications.create(
                        recipient_id=u.id,
                        type="ONBOARDING_REMINDER",
                        title="Finish your company profile",
                        body="Complete your company profile to start posting jobs.",
                    )
                    await db.commit()
                    sent += 1
                except Exception:
                    logger.exception(
                        "send_account_setup_reminders_task: failed to remind %s "
                        "(onboarding)",
                        u.email,
                    )

            for u in missing_kyc:
                try:
                    company_name = u.organization.company_name if u.organization else None
                    await email_service.send_kyc_reminder(
                        email=u.email,
                        first_name=u.first_name or "",
                        company_name=company_name or "",
                    )
                    await notifications.create(
                        recipient_id=u.id,
                        type="KYC_REMINDER",
                        title="Submit KYC documents",
                        body="Submit your verification documents to start posting jobs.",
                    )
                    await db.commit()
                    sent += 1
                except Exception:
                    logger.exception(
                        "send_account_setup_reminders_task: failed to remind %s "
                        "(KYC)",
                        u.email,
                    )

            logger.info(
                "send_account_setup_reminders_task: sent %d reminder(s).", sent
            )
    finally:
        await engine.dispose()
