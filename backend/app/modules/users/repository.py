"""Data-access layer for user records."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.modules.candidates.models import CandidateProfile
from app.modules.employer.enums import OrganizationRole
from app.modules.users.enums import UserRole
from app.modules.users.models import Organization, User, UserProfile
from app.modules.users.schemas import EmployerProfileUpdateRequest


class UserRepository:
    """Handles all database operations for User and UserProfile models."""

    def __init__(self, db):
        """Initialise with an async database session."""
        self._db = db

    async def get_user_by_email(self, email: str) -> User | None:
        """Return a user by email address, or None if not found."""
        stmt = (
            select(User)
            .where(User.email == email)
            .options(selectinload(User.organization))
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, id: UUID) -> User | None:
        """Return a user by UUID, or None if not found."""
        stmt = (
            select(User).where(User.id == id).options(selectinload(User.organization))
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

        For an EMPLOYER: if `organization_id` is present in `data`, the
        user joins that existing Organization as a MEMBER (a teammate
        accepting an invite). Otherwise a brand-new Organization is
        created with this user as its OWNER (a fresh employer
        registration). `invited_by_id`, if present, is stamped on the
        user regardless of which branch runs.

        Args:
            data: Dict of field values to pass to the User constructor.

        Returns:
            The newly created and refreshed User ORM instance.

        """
        # cv_sharing_consent/organization_id/invited_by_id aren't User
        # constructor fields — pulled out before construction.
        organization_id = data.get("organization_id")
        invited_by_id = data.get("invited_by_id")
        user_data = {
            k: v
            for k, v in data.items()
            if k not in ("cv_sharing_consent", "organization_id", "invited_by_id")
        }
        user = User(**user_data)
        if invited_by_id is not None:
            user.invited_by_id = invited_by_id
        self._db.add(user)
        await self._db.flush()

        profile = UserProfile(user_id=user.id)
        self._db.add(profile)
        await self._db.flush()

        if user.role == UserRole.EMPLOYER.value:
            if organization_id is not None:
                # Teammate joining an existing organization.
                user.organization_id = organization_id
                user.organization_role = OrganizationRole.MEMBER.value
                user.joined_organization_at = datetime.now(UTC)
            else:
                # Brand-new employer — creates and owns a fresh organization.
                organization = Organization(
                    created_by=user.id, is_profile_complete=False
                )
                self._db.add(organization)
                await self._db.flush()
                user.organization_id = organization.id
                user.organization_role = OrganizationRole.OWNER.value
                user.joined_organization_at = datetime.now(UTC)
            await self._db.flush()
        elif user.role == UserRole.CANDIDATE.value:
            candidate_profile = CandidateProfile(
                user_id=user.id,
                cv_sharing_consent=data.get("cv_sharing_consent", False),
            )
            self._db.add(candidate_profile)
            await self._db.flush()

            # Auto-enroll self-registered candidates in the talent pipeline
            from app.modules.talent_pool.enums import SourceType, TalentPoolStatus
            from app.modules.talent_pool.models import TalentPoolProfiles

            pool_entry = TalentPoolProfiles(
                candidate_profile_id=candidate_profile.id,
                added_by=user.id,  # candidate added themselves via registration
                source=SourceType.OTHER.value,
                status=TalentPoolStatus.NEW.value,
            )
            self._db.add(pool_entry)
            await self._db.flush()

        await self._db.refresh(user)
        return user

    async def get_employer_profile(self, user_id: UUID) -> Organization | None:
        """Return the Organization for a given user, or None."""
        stmt = (
            select(Organization)
            .join(User, User.organization_id == Organization.id)
            .where(User.id == user_id)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_employer_profile(
        self, user_id: UUID, data: EmployerProfileUpdateRequest
    ) -> Organization:
        """Create or update an organization's company profile and mark it complete.

        Required fields (company_name, industry, company_size) are always
        written. Optional fields are only written when provided.

        Args:
            user_id: The employer's user UUID.
            data: Validated profile payload from the request.

        Returns:
            The updated Organization ORM instance.

        """
        organization = await self.get_employer_profile(user_id)

        if organization is None:
            # Defensive — every employer should already have an
            # organization from registration. Create one if somehow missing.
            organization = Organization(created_by=user_id)
            self._db.add(organization)
            await self._db.flush()
            user = await self.get_user_by_id(user_id)
            user.organization_id = organization.id
            user.organization_role = OrganizationRole.OWNER.value
            user.joined_organization_at = datetime.now(UTC)

        organization.company_name = data.company_name
        organization.industry = data.industry
        organization.company_size = data.company_size

        if data.website is not None:
            organization.website = data.website

        if data.company_description is not None:
            organization.company_description = data.company_description

        # Flip the gate — required fields are now present
        organization.is_profile_complete = True

        await self._db.flush()
        await self._db.refresh(organization)
        return organization
