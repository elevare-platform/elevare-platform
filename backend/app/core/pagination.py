"""Cursor-based and offset-based pagination utilities.

Public interface:
- ``encode_cursor`` / ``decode_cursor``: opaque base64 cursor helpers.
- ``paginate_cursor``: keyset pagination for large, append-heavy result sets.
- ``paginate``: classic page/limit offset pagination.
- ``PageParams``: Pydantic model for page/limit query parameters.
"""

import base64
import math
from datetime import datetime
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.schemas import PaginationMeta, PaginationResponse

T = TypeVar("T")


def encode_cursor(created_at: datetime, id: UUID) -> str:
    """Encode (created_at, id) into a base64 URL-safe cursor string."""
    raw = f"{created_at.isoformat()}:{str(id)}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode a base64 URL-safe cursor string into (created_at, id).

    Raises:
        ValidationException: If the cursor string is malformed or cannot be decoded.

    """
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        # rsplit from the right once — datetime contains colons too
        created_at_str, id_str = raw.rsplit(":", 1)
        created_at = datetime.fromisoformat(created_at_str)
        return created_at, UUID(id_str)
    except Exception as exc:
        raise ValidationException(message="Invalid pagination cursor") from exc


async def paginate_cursor(
    query: Select,
    session: AsyncSession,
    cursor: str | None = None,
    limit: int = 20,
) -> dict:
    """Paginate a query using cursor-based (keyset) pagination.

    Args:
        query: The base SQLAlchemy SELECT statement (without ORDER BY or LIMIT).
        session: The async database session.
        cursor: Opaque cursor string from the previous page, or None for the first page.
        limit: Number of items per page (default 20, max 100).

    Returns:
        A dict with ``items``, ``next_cursor``, and ``count``.

    """
    if cursor:
        from sqlalchemy import tuple_

        created_at, last_id = decode_cursor(cursor)
        # Keyset filter: rows older than the cursor position
        query = query.where(
            tuple_(
                query.froms[0].c.created_at,
                query.froms[0].c.id,
            ) < tuple_(created_at, last_id)
        )

    # Fetch one extra item to detect whether a next page exists
    query = query.order_by(desc("created_at"), desc("id")).limit(limit + 1)

    result = await session.execute(query)
    items = result.scalars().all()

    has_next = len(items) > limit
    if has_next:
        items = items[:limit]

    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    return {
        "items": items,
        "next_cursor": next_cursor,
        "count": len(items),
    }


class PageParams(BaseModel):
    """Query parameters for offset-based pagination endpoints."""

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


async def paginate(
    query: Select,
    page: int,
    limit: int,
    session: AsyncSession,
) -> PaginationResponse:
    """Paginate a query using classic page/limit offset pagination.

    Args:
        query: The base SQLAlchemy SELECT statement.
        page: 1-based page number.
        limit: Number of items per page.
        session: The async database session.

    Returns:
        A ``PaginationResponse`` containing the items and pagination metadata.

    """
    offset = (page - 1) * limit

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query)

    result = await session.execute(query.offset(offset).limit(limit))
    items = result.scalars().all()

    total_pages = math.ceil(total / limit) if total > 0 else 1

    return PaginationResponse(
        message="OK",
        data=items,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total=total,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        ),
    )
