"""Application settings loaded from environment variables and .env file."""

import logging

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_INSECURE_SECRET_KEY_VALUES = {
    "",
    "dev-secret-key-change-in-production",
    "change-me-in-production",
    "secret",
}


class Settings(BaseSettings):
    """Centralised configuration for the Elevare API.

    All values are read from environment variables (case-insensitive).
    A ``.env`` file in the working directory is loaded automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Elevare API"
    app_version: str = "0.1.0"
    app_url: str = "http://localhost:5173"
    debug: bool = True
    environment: str = "development"

    # --- Persistence ---
    database_url: str
    redis_url: str

    # Security
    secret_key: str

    # JWT
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    algorithm: str = "HS256"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # Cookies
    cookie_secure: bool = False

    # Email Verification
    email_stub_mode: bool = True
    email_verification_token_expiry: int = 24

    # Invite Setting
    invite_expiry: int = 3

    # R2 Storage — all optional so app starts without R2 in CI
    r2_access_key_id: str | None = None
    r2_secret_access_key: str | None = None
    r2_bucket_name: str | None = None
    r2_endpoint_url: str | None = None
    r2_region: str = "auto"
    r2_public_url: str | None = None

    # Resend
    resend_api_key: str | None = None
    mail_from: str | None = None

    # Contact / Sitemap
    contact_email: str = "info_admin@elevare.com.ng"
    sales_email: str = "hr@elevare.com.ng"
    site_url: str = "https://elevare-platform.vercel.app/"

    # Claude API KEY
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # HMAC secret for CV text cache keys
    hmac_secret: str = "change-me-in-production"

    # AI scoring visibility — candidates never see ai_score unless this is True
    show_ai_score_to_candidates: bool = False
    # Default expiry for job access tokens in days
    default_access_token_expiry_days: int = 30

    # OpenAI
    openai_api_key: str | None = None

    # Sentry
    sentry_dsn: str | None = None

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse to start in production with insecure default values."""
        if self.environment != "production":
            return self

        errors = []

        if self.secret_key.lower() in _INSECURE_SECRET_KEY_VALUES or len(self.secret_key) < 32:
            errors.append("SECRET_KEY is insecure or too short (min 32 chars)")

        if self.hmac_secret in _INSECURE_SECRET_KEY_VALUES or len(self.hmac_secret) < 16:
            errors.append("HMAC_SECRET is insecure or too short (min 16 chars)")

        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true in production")

        if self.debug:
            errors.append("DEBUG must be false in production")

        if self.email_stub_mode:
            errors.append("EMAIL_STUB_MODE must be false in production")

        if any("localhost" in origin for origin in self.cors_origins):
            errors.append("CORS_ORIGINS contains localhost — remove before production deploy")

        if errors:
            raise ValueError(
                "Production security checks failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return self


settings = Settings()
