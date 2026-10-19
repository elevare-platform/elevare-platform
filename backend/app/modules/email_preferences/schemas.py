"""Request and response shapes for the email preferences endpoints."""

from pydantic import BaseModel


class EmailPreferenceResponse(BaseModel):
    """Whether an address receives emails from Elevare.

    ``email`` is masked (``a***@example.com``) when it comes from an unsubscribe link,
    and is the signed-in user's own address on ``/me``.
    """

    email: str
    emails_enabled: bool


class EmailPreferenceUpdate(BaseModel):
    emails_enabled: bool
