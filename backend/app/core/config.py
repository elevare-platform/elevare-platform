from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "Elevare API"
    app_version: str = "0.1.0"
    debug: bool = True
    environment: str = "development"

    # Database
    database_url: str

    # Security (populated in Phase 2)
    secret_key: str

    # JWT
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    algorithm: str = "HS256"

    # Cookies
    cookie_secure: bool = False

    # Email Verification
    email_stub_mode: bool = True
    email_verification_token_expiry: int = 24

    # Invite Setting
    invite_expiry: int = 3
    email_verification_token_expiry: int


settings = Settings()
