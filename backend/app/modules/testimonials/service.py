import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.storage import StorageService
from app.modules.testimonials.enums import TestimonialStatus
from app.modules.testimonials.models import Testimonial
from app.modules.testimonials.repository import TestimonialRepository
from app.modules.testimonials.schemas import (
    TestimonialAdminRead,
    TestimonialCreate,
    TestimonialModerationRequest,
    TestimonialRead,
    TestimonialResponse,
)

logger = logging.getLogger(__name__)


def _resolve_image_url(key: str | None) -> str | None:
    """Convert an R2 storage key to a publicly accessible URL."""
    if not key:
        return None
    if settings.r2_public_url:
        return f"{settings.r2_public_url.rstrip('/')}/{key}"
    return None  # no public URL configured — image won't display


def _to_read(t: Testimonial) -> TestimonialRead:
    return TestimonialRead(
        id=t.id,
        full_name=t.full_name,
        company=t.company,
        position=t.position,
        testimony=t.testimony,
        image_url=_resolve_image_url(t.image),
        created_at=t.created_at,
    )


def _to_admin_read(t: Testimonial) -> TestimonialAdminRead:
    return TestimonialAdminRead(
        id=t.id,
        full_name=t.full_name,
        company=t.company,
        position=t.position,
        testimony=t.testimony,
        image_url=_resolve_image_url(t.image),
        status=t.status,
        reviewed_at=t.reviewed_at,
        created_at=t.created_at,
    )

logger = logging.getLogger(__name__)


class TestimonialService:
    def __init__(self, db: AsyncSession, storage_service: StorageService) -> None:
        self._db = db
        self._repo = TestimonialRepository(db)
        self._storage = storage_service

    async def create_testimonial(
        self,
        full_name: str,
        testimony: str,
        company: str | None,
        position: str | None,
        image_bytes: bytes | None,
        image_content_type: str | None,
    ) -> TestimonialResponse:
        """Upload image to R2 (if provided) then persist the testimonial."""
        image_key: str | None = None

        if image_bytes and image_content_type:
            ext = image_content_type.split("/")[-1]  # jpeg | png | webp
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            image_key = f"testimonials/{timestamp}_{uuid.uuid4().hex[:8]}.{ext}"
            try:
                await self._storage.upload_file(image_bytes, image_key, image_content_type)
            except Exception:
                logger.exception("R2 upload failed for testimonial image key=%s", image_key)
                image_key = None  # don't block submission if upload fails

        data = TestimonialCreate(
            full_name=full_name,
            testimony=testimony,
            company=company,
            position=position,
            image=image_key,
        )
        await self._repo.create_testimonial(data)
        await self._db.commit()
        return TestimonialResponse(message="Testimonial submitted successfully.")

    async def get_testimonials(self) -> list[TestimonialRead]:
        """Return only approved testimonials — for public consumption."""
        testimonials = await self._repo.get_approved()
        return [_to_read(t) for t in testimonials]

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    async def admin_list_testimonials(
        self, status: TestimonialStatus | None
    ) -> list[TestimonialAdminRead]:
        """Return all testimonials, optionally filtered by status."""
        testimonials = await self._repo.get_all_by_status(status)
        return [_to_admin_read(t) for t in testimonials]

    async def moderate_testimonial(
        self, testimonial_id: UUID, data: TestimonialModerationRequest
    ) -> TestimonialAdminRead:
        """Set a testimonial's status to approved, rejected, or pending."""
        testimonial = await self._repo.get_by_id(testimonial_id)
        if not testimonial:
            raise NotFoundException(message="Testimonial not found.")

        updated = await self._repo.update_status(
            testimonial=testimonial,
            status=data.status,
            reviewed_at=datetime.now(UTC),
        )
        await self._db.commit()
        return _to_admin_read(updated)
