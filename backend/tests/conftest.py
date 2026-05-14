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
from app.modules.jobs.enums import ContractType, JobStatus, WorkModel
from app.modules.jobs.models import Job
from app.modules.users.enums import UserRole
from app.modules.users.models import User

test_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool
)


def make_user(**overrides) -> User:
    """Build an unsaved User instance with sensible defaults."""
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": f"user_{uuid4().hex[:8]}@example.com",
        "phone_number": f"0801{uuid4().int % 10**7:07d}",
        "password_hash": "hashed_password",
        "account_status": "ACTIVE",
    }

    data.update(overrides)
    return User(
        **data
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


def make_employer(**overrides) -> User:
    """Build an unsaved employer User instance."""
    return make_user(role=UserRole.EMPLOYER.value, **overrides)


def make_job(employer_id, **overrides) -> Job:
    """Build an unsaved Job instance with sensible defaults."""
    defaults = {
        "title": "Software Engineer",
        "description": "A great job opportunity for a skilled engineer.",
        "location": "Lagos, Nigeria",
        "contract_type": ContractType.FULL_TIME.value,
        "work_model": WorkModel.HYBRID.value,
        "status": JobStatus.ACTIVE.value,
        "employer_id": employer_id,
    }
    defaults.update(overrides)
    return Job(**defaults)

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
