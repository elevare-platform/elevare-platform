"""Application settings loaded from environment variables and .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Security (populated in Phase 2)
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
    email_verification_token_expiry: int

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


settings = Settings()
