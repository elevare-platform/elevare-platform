"""Running a query that needs a table or column a migration has not created yet.

On a deploy the new containers start BEFORE ``alembic upgrade head`` runs (docs: a migration runs on
live data after the new code is up), so for a few seconds new code can ask for a table that does not
exist yet. For the extras that only decorate a page (the "new" markers, a scoring profile, a score
report) that must not turn the page into an error: ``tolerate_missing`` runs the query in a
savepoint, and when the table or column is missing it gives back a fallback instead, leaving the
rest of the request's transaction usable. Any other error is raised as before.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

T = TypeVar("T")

# PostgreSQL's codes for "undefined table" and "undefined column".
_MISSING_CODES = {"42P01", "42703"}


def is_missing_schema(exc: DBAPIError) -> bool:
    """Whether the database refused because a table or column does not exist (yet)."""
    for candidate in (exc.orig, getattr(exc.orig, "__cause__", None)):
        code = getattr(candidate, "sqlstate", None) or getattr(candidate, "pgcode", None)
        if code in _MISSING_CODES:
            return True
    text = str(exc.orig).lower()
    return "does not exist" in text and ("relation" in text or "column" in text)


async def tolerate_missing(
    db: AsyncSession, operation: Callable[[], Awaitable[T]], fallback: T
) -> T:
    """Run ``operation`` in a savepoint; return ``fallback`` if the schema it needs is missing."""
    try:
        async with db.begin_nested():
            return await operation()
    except ProgrammingError as exc:
        if not is_missing_schema(exc):
            raise
        logger.warning("a table or column is not there yet (migration pending?): %s", exc.orig)
        return fallback
