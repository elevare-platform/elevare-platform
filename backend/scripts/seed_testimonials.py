"""Seed script — creates approved testimonials for the public homepage.

Idempotent: running this script multiple times will not duplicate data.
It checks for existing testimonials before inserting.

Usage (inside the api container):
    python scripts/seed_testimonials.py

Via docker compose (from project root):
    docker compose exec api python scripts/seed_testimonials.py

Via docker compose prod:
    docker compose -f docker-compose.prod.yml exec api python scripts/seed_testimonials.py
"""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

import app.core.model_registry  # noqa: F401
from app.core.database import AsyncSessionLocal
from app.modules.testimonials.enums import TestimonialStatus
from app.modules.testimonials.models import Testimonial

TESTIMONIALS = [
    {
        "full_name": "Chidinma Eze",
        "company": None,
        "position": None,
        "testimony": (
            "I used Elevare to look for a job and it worked well for me. "
            "I applied to a few roles and got called for interviews within "
            "two weeks. It made the whole process a lot easier."
        ),
        "status": TestimonialStatus.APPROVED.value,
        "created_at": datetime(2026, 7, 22, 10, 0, tzinfo=UTC),
    },
    {
        "full_name": "Tobiloba",
        "company": None,
        "position": None,
        "testimony": (
            "I had applied to a lot of places before with no luck. On "
            "Elevare I found roles that fit my experience and heard back "
            "from two of them in the same week."
        ),
        "status": TestimonialStatus.APPROVED.value,
        "created_at": datetime(2026, 7, 23, 14, 30, tzinfo=UTC),
    },
    {
        "full_name": "Ngozi",
        "company": None,
        "position": None,
        "testimony": (
            "I was not sure about the site at first, but the jobs I saw "
            "matched what I was looking for. I got a job about a month "
            "after signing up."
        ),
        "status": TestimonialStatus.APPROVED.value,
        "created_at": datetime(2026, 7, 25, 9, 15, tzinfo=UTC),
    },
    {
        "full_name": "Segun",
        "company": None,
        "position": None,
        "testimony": (
            "Signing up was simple and when I had a question about my "
            "application, someone actually replied. That does not happen "
            "a lot with other job sites."
        ),
        "status": TestimonialStatus.APPROVED.value,
        "created_at": datetime(2026, 7, 27, 16, 45, tzinfo=UTC),
    },
    {
        "full_name": "Amarachi",
        "company": None,
        "position": None,
        "testimony": (
            "I almost gave up on finding a job before I tried Elevare. "
            "Within a few weeks I had a role that matched what I studied "
            "and I am still there now."
        ),
        "status": TestimonialStatus.APPROVED.value,
        "created_at": datetime(2026, 7, 29, 11, 0, tzinfo=UTC),
    },
]


async def seed() -> None:
    """Create approved testimonials if none exist yet."""
    async with AsyncSessionLocal() as session:
        # Check if already seeded — idempotency guard
        result = await session.execute(
            select(Testimonial).where(
                Testimonial.full_name == TESTIMONIALS[0]["full_name"]
            )
        )
        if result.scalar_one_or_none():
            print("Seed data already exists. Skipping.")
            return

        for data in TESTIMONIALS:
            testimonial = Testimonial(**data, reviewed_at=data["created_at"])
            session.add(testimonial)

        await session.commit()
        print(f"Seeded {len(TESTIMONIALS)} testimonials.")


if __name__ == "__main__":
    asyncio.run(seed())
