"""Pydantic request and response schemas for the authentication app.

Request schemas validate and coerce inbound payloads for registration,
login, token refresh, email verification, and password management flows.

Response schemas define the outbound shapes for auth-related API responses.
"""

import re
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


def validate_password_strength(v: str) -> str:
    """Validate that a password meets the platform's strength requirements.

    Enforces a minimum length of 8 characters and requires at least one
    uppercase letter, one lowercase letter, one digit, and one special
    character.

    Args:
        v: The plain-text password string to validate.

    Returns:
        The original password string if all checks pass.

    Raises:
        ValueError: If any strength requirement is not met.

    """

    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")

    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")

    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")

    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")

    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', v):
        raise ValueError("Password must contain at least one special character")

    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Payload for creating a new user account.

    Attributes:
        first_name: User's given name, 2–100 characters.
        last_name: User's family name, 2–100 characters.
        email: Valid email address; used as the login identifier.
        phone_number: Nigerian mobile number in ``+234`` or ``0`` format.
        password: Plain-text password; must pass strength validation.
        confirm_password: Must match ``password`` exactly.

    """
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone_number: str = Field(..., min_length=8, max_length=15)
    password: str = Field(..., min_length=8)
    confirm_password: str = Field(..., exclude=True)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate that the phone number is a valid Nigerian mobile number.

        Args:
            v: The raw phone number string.

        Returns:
            The phone number string if it matches the expected pattern.

        Raises:
            ValueError: If the number does not match the Nigerian format.

        """
        pattern = r"^(\+234|0)[789]\d{9}$"
        if not re.match(pattern, v):
            raise ValueError("Invalid Nigerian phone number")
        return v


    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Delegate password strength validation to ``valid_password_strength``.

        Args:
            v: The plain-text password string.

        Returns:
            The validated password string.

        """
        return validate_password_strength(v)


    @model_validator(mode="after")
    def password_match(self) -> "RegisterRequest":
        """Ensure ``password`` and ``confirm_password`` are identical.

        Returns:
            The model instance if passwords match.

        Raises:
            ValueError: If the two password fields differ.

        """
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    """Payload for authenticating an existing user.

    Attributes:
        email: User's email address.
        password: Plain-text password.
    """
    email: EmailStr
    password: str = Field(..., min_length=1)


class RefreshRequest(BaseModel):
    """Payload for refreshing an access token using a refresh token.

    Attributes:
        refresh_token: The JWT refresh token issued during login.

    """
    refresh_token: str


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """Tokens returned after a successful login or token refresh.

    Attributes:
        access_token: Short-lived JWT for authenticating requests.
        refresh_token: Long-lived token used to obtain a new access token.
        token_type: Always ``"bearer"`` per the OAuth2 spec.

    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """User identity fields embedded in an authentication response.

    Attributes:
        id: The user's UUID primary key.
        first_name: User's given name.
        last_name: User's family name.
        email: User's email address.
        role: The user's permission role string.
        account_status: Current lifecycle state of the account.

    """

    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    account_status: str

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str


class MessageResponse(BaseModel):
    message: str

