"""Business logic for turning emails off and on."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.modules.email_preferences.models import SOURCE_EMAIL_LINK, SOURCE_SETTINGS
from app.modules.email_preferences.repository import EmailPreferenceRepository
from app.modules.email_preferences.tokens import normalize_email, read_unsubscribe_token


def mask_email(email: str) -> str:
    """``ada.lovelace@example.com`` -> ``a***@example.com``: enough for a person to
    recognise their own address on the page, not enough to read someone else's from a
    shared link."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}"


class EmailPreferenceService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = EmailPreferenceRepository(db)

    # --- by the signed link in an email (no login) -------------------------------

    @staticmethod
    def email_from_token(token: str) -> str:
        email = read_unsubscribe_token(token)
        if email is None:
            raise ValidationException(
                "This unsubscribe link is not valid.",
                code="INVALID_UNSUBSCRIBE_TOKEN",
                status_code=400,
            )
        return email

    async def preview(self, token: str) -> dict:
        """What the unsubscribe page shows before the person confirms."""
        email = self.email_from_token(token)
        return {
            "email": mask_email(email),
            "emails_enabled": not await self._repo.is_suppressed(email),
        }

    async def unsubscribe_by_token(self, token: str) -> dict:
        email = self.email_from_token(token)
        await self._repo.suppress(email, SOURCE_EMAIL_LINK)
        await self._db.commit()
        return {"email": mask_email(email), "emails_enabled": False}

    async def resubscribe_by_token(self, token: str) -> dict:
        email = self.email_from_token(token)
        await self._repo.unsuppress(email)
        await self._db.commit()
        return {"email": mask_email(email), "emails_enabled": True}

    # --- by a signed-in user, for their own address -------------------------------

    async def get_for_account(self, account_email: str) -> dict:
        email = normalize_email(account_email)
        return {"email": email, "emails_enabled": not await self._repo.is_suppressed(email)}

    async def set_for_account(self, account_email: str, enabled: bool) -> dict:
        email = normalize_email(account_email)
        if enabled:
            await self._repo.unsuppress(email)
        else:
            await self._repo.suppress(email, SOURCE_SETTINGS)
        await self._db.commit()
        return {"email": email, "emails_enabled": enabled}
