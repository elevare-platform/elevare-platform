"""Celery tasks for the users module: self-healing role-switch backstop.

Mirrors billing/tasks.py's reconcile_pending_payments_task shape: one
periodic sweep, its own engine, disposed in a finally block.
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.celery_app import celery
from app.core.config import settings
from app.core.email import get_email_service
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


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
