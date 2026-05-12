from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import app.core.model_registry  # noqa: F401
from app.core.config import settings
from app.core.dependencies import get_db
from app.main import app
from app.modules.auth.schemas import RegisterRequest
from app.modules.users.models import User

test_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool
)


def make_user(**overrides) -> User:
    """Build an unsaved User instance with sensible defaults."""
    return User(
        first_name="John",
        last_name="Doe",
        email=f"user_{uuid4().hex[:8]}@example.com",
        phone_number=f"0801{uuid4().int % 10**7:07d}",
        password_hash="hashed_password",
        **overrides,
    )

def make_register_data(**overrides) -> RegisterRequest:
    """Build a RegisterRequest with unique email/phone and sensible defaults."""
    defaults = {
        "first_name": "John",
        "last_name": "Doe",
        "email": f"user_{uuid4().hex[:8]}@example.com",
        "phone_number": f"0801{uuid4().int % 10**7:07d}",
        "password": "Password123#",
        "confirm_password": "Password123#",
    }
    defaults.update(overrides)
    return RegisterRequest(**defaults)


def future(minutes: int = 30) -> datetime:
    """Return a timezone-aware UTC datetime ``minutes`` in the future."""
    return datetime.now(UTC) + timedelta(minutes=minutes)

@pytest_asyncio.fixture
async def db_session():
    """Provide a DB session that rolls back after each test."""
    async with test_engine.connect() as connection:
        await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            yield session
        await connection.rollback()

@pytest_asyncio.fixture
async def client(db_session):
    """Async HTTP client with DB dependency overridden to use test session."""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
