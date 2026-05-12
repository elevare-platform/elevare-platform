import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)

class UserService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._user_repo = UserRepository(db)


