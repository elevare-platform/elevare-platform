"""The "must change password" flag on a user.

An account Elevare provisions with a temporary password carries this flag until
its owner sets their own password.

The flag is read and written through a small hand-written table description, not
the ``User`` model, on purpose: the column is added by a migration that runs after
the new containers are already serving requests, and a model attribute would make
every query that loads a user select a column that may not exist yet. Reading
here therefore treats a missing column as "no change required".
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

_users = sa.table(
    "users",
    sa.column("id", sa.UUID),
    sa.column("must_change_password", sa.Boolean),
)


async def must_change_password(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """Whether this user must set a new password before doing anything else.

    False for an unknown user, and False while the column does not exist yet (the
    seconds between a deploy starting the new code and its migration finishing),
    so a login never fails because of a column that is still being added.
    """
    try:
        # A savepoint: when the column is missing the database rejects the query,
        # and without it the caller's whole transaction would be left unusable.
        async with db.begin_nested():
            result = await db.execute(
                sa.select(_users.c.must_change_password).where(_users.c.id == user_id)
            )
            return bool(result.scalar_one_or_none())
    except ProgrammingError:
        return False


async def set_must_change_password(
    db: AsyncSession, user_id: uuid.UUID, value: bool
) -> None:
    """Set or clear the flag. Does not commit: the caller owns the transaction."""
    await db.execute(
        sa.update(_users)
        .where(_users.c.id == user_id)
        .values(must_change_password=value)
    )
