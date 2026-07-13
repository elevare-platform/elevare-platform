from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.testimonials.enums import TestimonialStatus
from app.modules.testimonials.models import Testimonial
from app.modules.testimonials.schemas import TestimonialCreate


class TestimonialRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_testimonial(self, data: TestimonialCreate) -> Testimonial:
        db_testimonial = Testimonial(**data.model_dump())
        self._db.add(db_testimonial)
        await self._db.flush()
        return db_testimonial

    async def get_approved(self) -> list[Testimonial]:
        result = await self._db.execute(
            select(Testimonial)
            .where(Testimonial.status == TestimonialStatus.APPROVED)
            .order_by(Testimonial.reviewed_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_by_status(
        self, status: TestimonialStatus | None
    ) -> list[Testimonial]:
        stmt = select(Testimonial).order_by(Testimonial.created_at.desc())
        if status:
            stmt = stmt.where(Testimonial.status == status)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, testimonial_id: UUID) -> Testimonial | None:
        result = await self._db.execute(
            select(Testimonial).where(Testimonial.id == testimonial_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, testimonial: Testimonial, status: TestimonialStatus, reviewed_at: datetime
    ) -> Testimonial:
        testimonial.status = status.value
        testimonial.reviewed_at = reviewed_at
        await self._db.flush()
        return testimonial
