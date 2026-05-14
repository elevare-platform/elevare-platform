"""Data-access layer for user records."""

from uuid import UUID

from sqlalchemy import select

from app.modules.users.models import User, UserProfile


class UserRepository:
    """Handles all database operations for User and UserProfile models."""

    def __init__(self, db):
        self._db = db

    async def get_user_by_email(self, email: str) -> User | None:
        """Return a user by email address, or None if not found."""
        stmt = select(User).where(User.email == email)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, id: UUID) -> User | None:
        """Return a user by UUID, or None if not found."""
        stmt = select(User).where(User.id == id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_phone(self, phone: str) -> User | None:
        """Return a user by phone number, or None if not found."""
        stmt = select(User).where(User.phone_number == phone)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, data: dict) -> User:
        """Create a new user and an empty UserProfile, then return the user.

        Args:
            data: Dict of field values to pass to the User constructor.

        Returns:
            The newly created and refreshed User ORM instance.

        """
        user = User(**data)
        self._db.add(user)
        await self._db.flush()

        profile = UserProfile(user_id=user.id)
        self._db.add(profile)
        await self._db.flush()

        await self._db.refresh(user)
        return user


