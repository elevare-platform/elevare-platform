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
    app_version: str
    app_url: str
    debug: bool
    environment: str

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
    cors_origins: list[str]

    # Cookies
    cookie_secure: bool

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
    sales_email: str = "recruitment@elevare.com.ng"
    site_url: str = "https://elevare-platform.vercel.app/"

    # Claude API KEY
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # HMAC secret for CV text cache keys
    hmac_secret: str

    # AI scoring visibility — candidates never see ai_score unless this is True
    show_ai_score_to_candidates: bool = False
    # Default expiry for job access tokens in days
    default_access_token_expiry_days: int = 30

    # Master switch for every Starter/Professional plan gate (job posting
    # limit, talent pool visibility cap, candidate search block, scoring
    # gates — all of them read BillingService.get_effective_plan, so this
    # one flag controls all of them at once). MUST stay True in production —
    # this exists so gating can be switched off during testing without
    # touching individual orgs' subscriptions.
    plan_gates_enabled: bool

    # Master switch for the KYC-required-to-post-a-job gate (JobService.
    # create_job). When False, an employer can post without an APPROVED
    # kyc_status — everything else (the self-serve upload/submit flow at
    # /employer/verification, admin review/approval) still works exactly
    # the same; this only controls whether posting is blocked on the
    # result. Turning this back on does NOT strand employers who signed up
    # while it was off — kyc_status still defaults to NOT_SUBMITTED for
    # everyone, and the existing /employer/verification page (already
    # built, unaffected by this flag) is how any employer, old or new,
    # gets from NOT_SUBMITTED to APPROVED. The PostJobPage banner that
    # links there on a KYC_REQUIRED error is what surfaces this to them.
    kyc_enforcement_enabled: bool

    # OpenAI
    openai_api_key: str | None = None

    # AI video interviews — live realtime voice conversation
    realtime_model: str
    transcription_model: str
    interview_max_duration_minutes: int
    interview_video_retention_days: int

    # Sentry
    sentry_dsn: str | None = None

    # Gmail OAuth — required for Phase 16A ingestion
    gmail_client_id: str | None = None
    gmail_client_secret: str | None = None
    gmail_redirect_uri: str

    # Zoho Mail OAuth — required for Phase 16B ingestion
    # accounts_url varies by region:
    #   Global: https://accounts.zoho.com
    #   EU:     https://accounts.zoho.eu
    #   India:  https://accounts.zoho.in
    #   AU:     https://accounts.zoho.com.au
    zoho_client_id: str | None = None
    zoho_client_secret: str | None = None
    zoho_redirect_uri: str
    zoho_accounts_url: str
    
    # Fernet key for encrypting OAuth tokens at rest
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    fernet_key: str | None = None

    # Paystack — primary payment provider (billing module)
    paystack_secret_key: str | None = None
    paystack_public_key: str | None = None

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """Refuse to start in production with insecure default values."""
        if self.environment != "production":
            return self

        errors = []

        if (
            self.secret_key.lower() in _INSECURE_SECRET_KEY_VALUES
            or len(self.secret_key) < 32
        ):
            errors.append("SECRET_KEY is insecure or too short (min 32 chars)")

        if (
            self.hmac_secret in _INSECURE_SECRET_KEY_VALUES
            or len(self.hmac_secret) < 16
        ):
            errors.append("HMAC_SECRET is insecure or too short (min 16 chars)")

        if not self.cookie_secure:
            errors.append("COOKIE_SECURE must be true in production")

        if self.debug:
            errors.append("DEBUG must be false in production")

        if self.email_stub_mode:
            errors.append("EMAIL_STUB_MODE must be false in production")

        if any("localhost" in origin for origin in self.cors_origins):
            errors.append(
                "CORS_ORIGINS contains localhost — remove before production deploy"
            )

        if errors:
            raise ValueError(
                "Production security checks failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

        return self


settings = Settings()
