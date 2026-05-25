"""Data-access layer for user records."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.candidates.models import CandidateProfile
from app.modules.users.enums import UserRole
from app.modules.users.models import EmployerProfile, User, UserProfile
from app.modules.users.schemas import EmployerProfileUpdateRequest


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
        stmt = select(User).where(User.id == id).options(
            selectinload(User.employer_profile)
        )
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

        if user.role == UserRole.EMPLOYER.value:
            employer_profile = EmployerProfile(user_id=user.id)
            employer_profile.is_profile_complete = False
            self._db.add(employer_profile)
            await self._db.flush()
        elif user.role == UserRole.CANDIDATE.value:
            candidate_profile = CandidateProfile(user_id=user.id)
            self._db.add(candidate_profile)
            await self._db.flush()

        await self._db.refresh(user)
        return user

    async def get_employer_profile(self, user_id: UUID) -> EmployerProfile | None:
        """Return the EmployerProfile for a given user, or None."""
        stmt = select(EmployerProfile).where(EmployerProfile.user_id == user_id)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_employer_profile(
        self, user_id: UUID, data: EmployerProfileUpdateRequest
    ) -> EmployerProfile:
        """Create or update an employer profile and mark it complete.

        Required fields (company_name, industry, company_size) are always
        written. Optional fields are only written when provided.

        Args:
            user_id: The employer's user UUID.
            data: Validated profile payload from the request.

        Returns:
            The updated EmployerProfile ORM instance.

        """
        profile = await self.get_employer_profile(user_id)

        if profile is None:
            profile = EmployerProfile(user_id=user_id)
            self._db.add(profile)

        profile.company_name = data.company_name
        profile.industry = data.industry
        profile.company_size = data.company_size

        if data.website is not None:
            profile.website = data.website

        if data.company_description is not None:
            profile.company_description = data.company_description

        # Flip the gate — required fields are now present
        profile.is_profile_complete = True

        await self._db.flush()
        await self._db.refresh(profile)
        return profile


