from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import mapped_column, Mapped
from app.core.database import BaseModel
from .enums import TestimonialStatus


class Testimonial(BaseModel):
    __tablename__ = "testimonials"

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    company: Mapped[str | None] = mapped_column(String(150), nullable=True)
    position: Mapped[str | None] = mapped_column(String(150), nullable=True)
    testimony: Mapped[str] = mapped_column(Text, nullable=False)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(TestimonialStatus, name="testimonialstatus", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TestimonialStatus.PENDING.value,
        server_default=TestimonialStatus.PENDING.value,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
