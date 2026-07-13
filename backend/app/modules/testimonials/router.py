import logging

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.storage import StorageService, get_storage_service
from app.modules.testimonials.schemas import TestimonialRead, TestimonialResponse
from app.modules.testimonials.service import TestimonialService

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB


def get_testimonial_service(
    db: AsyncSession = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
) -> TestimonialService:
    return TestimonialService(db, storage_service)


@router.post("", status_code=201, response_model=TestimonialResponse)
async def create_testimonial(
    full_name: str = Form(...),
    testimony: str = Form(...),
    company: str | None = Form(default=None),
    position: str | None = Form(default=None),
    image: UploadFile | None = File(default=None),
    service: TestimonialService = Depends(get_testimonial_service),
) -> TestimonialResponse:
    """Submit a testimonial. Image is optional (JPEG/PNG/WebP, max 5 MB)."""
    from fastapi import HTTPException

    if not full_name or not full_name.strip():
        raise HTTPException(status_code=422, detail="full_name cannot be empty.")
    if not testimony or not testimony.strip():
        raise HTTPException(status_code=422, detail="testimony cannot be empty.")

    image_bytes: bytes | None = None
    image_content_type: str | None = None

    if image and image.filename:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400, detail="Image must be JPEG, PNG, or WebP."
            )
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=400, detail="Image must be under 5 MB.")
        image_content_type = image.content_type

    return await service.create_testimonial(
        full_name=full_name,
        testimony=testimony,
        company=company,
        position=position,
        image_bytes=image_bytes,
        image_content_type=image_content_type,
    )


@router.get("", response_model=list[TestimonialRead])
async def list_testimonials(
    service: TestimonialService = Depends(get_testimonial_service),
) -> list[TestimonialRead]:
    """Retrieve all testimonials, most recent first."""
    return await service.get_testimonials()
