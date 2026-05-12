import math
from typing import TypeVar

from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.schemas import PaginationMeta, PaginationResponse

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


async def paginate(query: Select, page: int, limit: int, session: AsyncSession) -> PaginationResponse:
    # calculate offset
    offset = (page - 1) * limit

    # Get total count
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
            has_previous=page > 1
        )
    )
