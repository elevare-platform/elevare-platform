"""Pydantic schemas for the users module."""

from pydantic import BaseModel, ConfigDict, field_validator


class EmployerProfileUpdateRequest(BaseModel):
    """Payload for creating or updating an employer's company profile.

    All fields except ``company_name`` and ``industry`` are optional so the
    endpoint can be used for both initial onboarding and later edits.
    """

    company_name: str
    industry: str
    company_size: str
    website: str | None = None
    company_description: str | None = None

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Company name must be at least 2 characters")
        return v

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Industry is required")
        return v

    @field_validator("company_size")
    @classmethod
    def validate_company_size(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Company size is required")
        return v

    @field_validator("website")
    @classmethod
    def validate_website(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip()
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Website must start with http:// or https://")
        return v


class EmployerProfileResponse(BaseModel):
    """Employer profile fields returned after a successful update."""

    company_name: str | None
    industry: str | None
    company_size: str | None
    website: str | None
    company_logo_url: str | None
    is_profile_complete: bool

    model_config = ConfigDict(from_attributes=True)
