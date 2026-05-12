from uuid import UUID

from sqlalchemy import select

from app.modules.users.models import User, UserProfile


class UserRepository:
    def __init__(self, db):
        self._db = db

    async def get_user_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()
        return user

    async def get_user_by_id(self, id: UUID) -> User | None:
        stmt = select(User).where(User.id == id)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()
        return user

    async def get_user_by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone_number == phone)
        result = await self._db.execute(stmt)
        user = result.scalar_one_or_none()
        return user

    async def create_user(self, data: dict) -> User:
        user = User(**data)
        self._db.add(user)
        await self._db.flush()

        profile = UserProfile(
            user_id=user.id
        )
        self._db.add(profile)
        await self._db.flush()

        await self._db.refresh(user)

        return user


