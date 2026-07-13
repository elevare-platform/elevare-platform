"""Domain exceptions for the Elevare platform.

All exceptions inherit from ``PlatformError``, which carries the HTTP status
code, machine-readable ``code``, and human-readable ``message`` needed by the
global exception handler to build a consistent ``ErrorResponse``.
"""


class PlatformError(Exception):
    """Base class for all application-level exceptions.

    Attributes
    ----------
        message: Human-readable description of the error.
        code: Upper-snake-case machine-readable identifier (e.g. ``NOT_FOUND``).
        status_code: HTTP status code to return to the client.
        details: Optional list of field-level error detail objects.

    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: list | None = None,
    ) -> None:
        """Set error attributes and pass the message to the base Exception."""
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)


# ---------------------------------------------------------------------------
# Authentication  (HTTP 401 / 403)
# ---------------------------------------------------------------------------


class InvalidCredentialsException(PlatformError):
    """Raised when email/password credentials do not match any account."""

    def __init__(
        self,
        message: str = "Invalid credentials",
        code: str = "INVALID_CREDENTIALS",
        status_code: int = 401,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class TokenExpiredException(PlatformError):
    """Raised when a JWT access or refresh token has passed its expiry time."""

    def __init__(
        self,
        message: str = "Token expired",
        code: str = "TOKEN_EXPIRED",
        status_code: int = 401,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class TokenInvalidException(PlatformError):
    """Raised when a JWT is malformed, has a bad signature, or wrong type."""

    def __init__(
        self,
        message: str = "Token is invalid",
        code: str = "TOKEN_INVALID",
        status_code: int = 401,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class RevokedTokenException(PlatformError):
    """Raised when a refresh token has already been revoked (used or logged out)."""

    def __init__(
        self,
        message: str = "Token revoked",
        code: str = "TOKEN_REVOKED",
        status_code: int = 401,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class RefreshTokenMissing(PlatformError):
    """Raised when a refresh token is expected but not present in the request."""

    def __init__(
        self,
        message: str = "Refresh token is missing",
        code: str = "REFRESH_TOKEN_MISSING",
        status_code: int = 401,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class EmailNotVerifiedException(PlatformError):
    """Raised when an action requires a verified email but the user has not verified."""

    def __init__(
        self,
        message: str = "Email not verified",
        code: str = "EMAIL_NOT_VERIFIED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class AlreadyExistsException(PlatformError):
    """Raised when attempting to create a resource that already exists."""

    def __init__(
        self,
        message: str = "Resource already exists",
        code: str = "ALREADY_EXISTS",
        status_code: int = 409,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class AccountSuspendedException(PlatformError):
    """Raised when a suspended account attempts to authenticate or access a resource."""

    def __init__(
        self,
        message: str = "Account suspended. Contact support.",
        code: str = "ACCOUNT_SUSPENDED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class AccountBannedException(PlatformError):
    """Raised when a permanently banned account attempts to authenticate."""

    def __init__(
        self,
        message: str = "Account banned",
        code: str = "ACCOUNT_BANNED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class AccountDeactivatedException(PlatformError):
    """Raised when a deactivated account attempts to authenticate."""

    def __init__(
        self,
        message: str = "Account deactivated",
        code: str = "ACCOUNT_DEACTIVATED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class AccountSetupIncompleteException(PlatformError):
    """Raised when an invited user accesses a resource before completing account setup."""

    def __init__(
        self,
        message: str = "Account setup incomplete",
        code: str = "ACCOUNT_SETUP_INCOMPLETE",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class EmailVerificationRequiredException(PlatformError):
    """Raised when a user with PENDING_VERIFICATION status accesses a protected route."""

    def __init__(
        self,
        message: str = "Email verification required",
        code: str = "EMAIL_VERIFICATION_REQUIRED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class TokenAlreadyUsedException(PlatformError):
    """Raised when a verification or invite token has already been consumed."""

    def __init__(
        self,
        message: str = "Token has already been used",
        code: str = "TOKEN_ALREADY_USED",
        status_code: int = 400,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class VerificationTokenExpiredException(PlatformError):
    """Raised when a verification or invite token has passed its expiry time."""

    def __init__(
        self,
        message: str = "Verification token has expired",
        code: str = "VERIFICATION_TOKEN_EXPIRED",
        status_code: int = 400,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class CVErrorException(PlatformError):
    """Raised when an error occurs during CV processing."""

    def __init__(
        self,
        message: str = "CV processing error",
        code: str = "CV_ERROR",
        status_code: int = 500,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Authorization  (HTTP 403)
# ---------------------------------------------------------------------------


class PermissionDeniedException(PlatformError):
    """Raised when an authenticated user lacks the required role or ownership."""

    def __init__(
        self,
        message: str = "Permission denied",
        code: str = "PERMISSION_DENIED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class ProfileIncompleteException(PermissionDeniedException):
    """Raised when an employer tries to post a job without a complete profile."""

    def __init__(
        self,
        message: str = "Complete your company profile before posting jobs",
        code: str = "PERMISSION_DENIED",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Not Found  (HTTP 404)
# ---------------------------------------------------------------------------


class NotFoundException(PlatformError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class UserNotFoundException(NotFoundException):
    """Raised when a user ID from a JWT payload no longer exists in the database."""

    def __init__(
        self,
        message: str = "User not found",
        code: str = "USER_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class JobNotFoundError(NotFoundException):
    """Raised when a job ID does not match any record in the database."""

    def __init__(
        self,
        message: str = "Job not found",
        code: str = "JOB_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class ProfileNotFoundException(NotFoundException):
    """Raised when a candidate or employer profile is not found."""

    def __init__(
        self,
        message: str = "Profile not found",
        code: str = "PROFILE_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class DocumentNotFoundError(NotFoundException):
    """Raised when a CV or supporting document record is not found."""

    def __init__(
        self,
        message: str = "Document not found",
        code: str = "DOCUMENT_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class ApplicationNotFound(NotFoundException):
    """Raised when an application record is not found."""

    def __init__(
        self,
        message: str = "Application not found",
        code: str = "APPLICATION_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class SubmissionNotFound(NotFoundException):
    """Raised when a CV submission record is not found."""

    def __init__(
        self,
        message: str = "Submission not found",
        code: str = "SUBMISSION_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class TokenNotFoundError(NotFoundException):
    """Raised when a token record cannot be found by its identifier."""

    def __init__(
        self,
        message: str = "Token not found",
        code: str = "TOKEN_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Validation  (HTTP 422)
# ---------------------------------------------------------------------------


class ValidationException(PlatformError):
    """Raised for business-rule validation failures (e.g. invalid state transitions)."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_FAILED",
        status_code: int = 422,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Job Exceptions
# ---------------------------------------------------------------------------
class JobApplicationEnded(PlatformError):
    """Raised when the job application deadline has passed."""

    def __init__(
        self,
        message: str = "Job application deadline has passed.",
        code: str = "JOB_DEADLINE_PAST",
        status_code: int = 422,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class AlreadyApplied(PlatformError):
    """Raised when a candidate tries to apply to a job they already applied for."""

    def __init__(
        self,
        message: str = "You already applied for this job",
        code: str = "ALREADY_APPLIED",
        status_code: int = 409,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


# --- Application Status Errors
class ApplicationWithdrawalError(PlatformError):
    """Raised when a candidate attempts an invalid application withdrawal."""

    def __init__(
        self,
        message: str = "You can't withdraw your application for this particular job",
        code: str = "WITHDRAWAL_ERROR",
        status_code: int = 409,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class InvalidStatus(PlatformError):
    """Raised when an invalid application status transition is attempted."""

    def __init__(
        self,
        message: str = "Valid Transition Error",
        code: str = "INVALID_STATUS_TRANSITION",
        status_code: int = 400,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class CandidateProfileIncompleteException(PlatformError):
    """Raised when a candidate tries to apply without completing their profile."""

    def __init__(
        self,
        message: str = "Complete your profile before applying to jobs",
        code: str = "PROFILE_INCOMPLETE",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)


class CannotModifyAdminException(PlatformError):
    """Raised when an admin attempts to modify another admin account."""

    def __init__(
        self,
        message: str = "Admin accounts cannot be modified by other admins",
        code: str = "CANNOT_MODIFY_ADMIN",
        status_code: int = 403,
        details: list | None = None,
    ) -> None:
        """Initialise with platform error defaults."""
        super().__init__(message, code, status_code, details)
