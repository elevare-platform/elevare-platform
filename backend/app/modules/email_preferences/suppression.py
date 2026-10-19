"""Which of these addresses have turned emails off? (the check the email sender makes)

The email service has no database session of its own and runs inside request handlers
and Celery tasks alike (a task makes a new event loop per run), so this opens its own
short-lived connection instead of borrowing one. That is a connection per email sent,
which is nothing next to the cost of sending the email.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.modules.email_preferences.models import EmailSuppression
from app.modules.email_preferences.tokens import normalize_email

logger = logging.getLogger(__name__)

# PostgreSQL's code for "this table does not exist".
_UNDEFINED_TABLE = "42P01"


def _is_missing_table(exc: ProgrammingError) -> bool:
    original = exc.orig
    sqlstate = getattr(original, "sqlstate", None) or getattr(
        getattr(original, "__cause__", None), "sqlstate", None
    )
    return sqlstate == _UNDEFINED_TABLE


async def suppressed_addresses(addresses: list[str]) -> set[str]:
    """The lower-cased addresses, among those given, that have turned emails off.

    If the table does not exist yet, nobody has unsubscribed: on a deploy the new code
    can run for a few seconds before the migration that creates it finishes. That case
    is logged and treated as "no one unsubscribed". Any other database error is raised,
    like any other failure to deliver an email.
    """
    wanted = {normalize_email(address) for address in addresses}
    if not wanted:
        return set()

    engine = create_async_engine(
        settings.database_url, poolclass=NullPool, pool_pre_ping=True
    )
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(
                select(EmailSuppression.email).where(EmailSuppression.email.in_(wanted))
            )
            return set(rows.scalars().all())
    except ProgrammingError as exc:
        if not _is_missing_table(exc):
            raise
        logger.warning(
            "email_suppressions table is missing (migration not applied yet?); "
            "sending without the unsubscribe check"
        )
        return set()
    finally:
        await engine.dispose()
