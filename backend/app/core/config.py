"""Application settings loaded from environment variables and .env file."""

import logging
from typing import Literal

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
    # The public URL of THIS API (for example https://api.example.com), without a
    # trailing slash. Used for the one-click "List-Unsubscribe" header in emails:
    # a mail client posts to it directly, so it must be the API's address, not the
    # website's. Optional: when unset, emails still carry the Unsubscribe link in
    # the footer, just not the mail client's own Unsubscribe button.
    api_public_url: str | None = None
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

    # Tiered AI model routing — the fast/cheap model used as a first pass for
    # CV extraction and fit reasoning, escalating to anthropic_model (Sonnet)
    # only when the fast model's own output signals it's a hard/important case.
    anthropic_model_fast: str = "claude-haiku-4-5"
    ai_tiering_enabled: bool = True
    # Below this average field_confidence, a Haiku CV extraction is re-run on Sonnet.
    ai_cv_confidence_escalation_threshold: float = 0.75
    # Haiku fit-reasoning scores inside this [low, high] band are re-run on Sonnet —
    # start wide (conservative) and narrow once real escalation-rate data comes in.
    ai_fit_score_escalation_band: tuple[int, int] = (35, 100)
    anthropic_model_fast: str = "claude-haiku-4-5"
    ai_tiering_enabled: bool = True
    ai_cv_confidence_escalation_threshold: float = 0.65
    ai_fit_score_escalation_threshold: int = 40

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
    # Off switch for AI interviews. When false, no new invites are sent and no
    # new live session can start. Interviews already in progress can still
    # upload and be scored, so a candidate mid-interview is never cut off.
    interview_enabled: bool = True
    # Lets the AI interviewer end the session itself once it has covered the
    # brief, instead of running to the time limit. When false the interviewer is
    # only told to wrap up and the candidate presses End. The "time is a ceiling,
    # not a target" instructions apply either way.
    interview_ai_can_end_early: bool = True
    # Most first-time invites one organization (or one account that has no
    # organization) can send in any rolling 24 hours. Each invite can become a
    # live OpenAI Realtime session, the largest cost of the feature, so this
    # bounds the spend. Resends are not counted. 0 means no limit.
    interview_daily_invite_limit: int = 30
    # Credits an AI interview costs the organization that owns the job, taken at
    # the first invite (a resend is free) and given back if the invite expires
    # unused or the interview fails on our side. Elevare's own admin-owned jobs
    # are never charged. 0 switches charging off, without a deploy.
    interview_credit_cost: int = 10
    # After an interview, transcribe the recording on the server and compare it
    # with the transcript the candidate's browser submitted. Costs one Whisper
    # call per interview (about $0.006 per audio minute). Set to false to fall
    # back to trusting the submitted transcript, without a deploy.
    interview_transcript_crosscheck_enabled: bool = True

    # Which interview NEW invitations use (docs/08_DECISIONS.md, "The new strict, text-only
    # AI interview"). "live" is the existing live voice conversation, and stays the default
    # until the strict interview is built and has been through its reviews. "strict" is the
    # proctored interview with questions shown as text. The old one is kept in the code only
    # so this can be switched back with no rebuild. An interview keeps the style it was
    # invited with.
    interview_style: Literal["live", "strict"] = "live"
    # The strict interview's limits (the user's decisions): 20 minutes in all, and the
    # employer sets 5 questions by default, up to 6, which fits that cap.
    strict_interview_max_minutes: int = 20
    strict_interview_max_questions: int = 6
    strict_interview_default_questions: int = 5
    # A follow-up question gets its own, shorter allowance. It is only asked while the
    # interview has at least this many seconds left, so it can never squeeze out the next
    # real question; the allowance is also never longer than the time left.
    strict_follow_up_seconds: int = 90
    strict_follow_up_min_remaining_seconds: int = 120
    # How much audio one answer may upload (the longest answer is 10 minutes of speech,
    # which is a few MB; this only stops an absurd file).
    strict_answer_max_bytes: int = 15 * 1024 * 1024
    # A candidate whose page reloads keeps what was recorded so far in their browser and sends
    # it as a separate part, to be joined into one video. This bounds how many parts one
    # interview may have (each reload makes one).
    strict_recording_max_parts: int = 8
    # Leaving the interview screen (the page hidden, the window out of focus, full screen
    # exited): the 1st to 3rd leave warns, the 4th ends the interview, and so does 60 seconds
    # away in total (the user's decisions, option B "Balanced"). Key presses only warn.
    strict_max_leaves: int = 4
    strict_max_away_seconds: int = 60
    # Minimum share (0.0-1.0) of the submitted transcript's word pairs that must
    # also appear in the recording's own transcript. An unmeasured starting
    # point: calibrate it against real interviews via the match_score stored in
    # interview_transcript_checks.
    interview_transcript_match_threshold: float = 0.40

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
