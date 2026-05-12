class PlatformError(Exception):
    def __init__(
        self,
        message: str,
        code: str,
        status_code: int,
        details: list | None = None
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []
        super().__init__(message)

# ---------------------------------------------------------------------------
# Authentication  (HTTP 401 / 403)
# ---------------------------------------------------------------------------

class InvalidCredentialsException(PlatformError):
    def __init__(
        self,
        message: str = "Invalid credentials",
        code: str = "INVALID_CREDENTIALS",
        status_code: int = 401,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


class TokenExpiredException(PlatformError):
    def __init__(
        self,
        message: str = "Token expired",
        code: str = "TOKEN_EXPIRED",
        status_code: int = 401,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)

class TokenInvalidException(PlatformError):

    def __init__(
        self,
        message: str = "Token is invalid",
        code: str = "TOKEN_INVALID",
        status_code: int = 401,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


class RevokedTokenException(PlatformError):
    def __init__(
        self,
        message: str = "Token revoked",
        code: str = "TOKEN_REVOKED",
        status_code: int = 401,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


class EmailNotVerifiedException(PlatformError):
    def __init__(
        self,
        message: str = "Email not verified",
        code: str = "EMAIL_NOT_VERIFIED",
        status_code: int = 403,
        details: list | None = None
    ) -> None:
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
        super().__init__(message, code, status_code, details)


class AccountSuspendedException(PlatformError):

    def __init__(
        self,
        message: str = "Account suspended",
        code: str = "ACCOUNT_SUSPENDED",
        status_code: int = 403,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


class AccountBannedException(PlatformError):
    def __init__(
        self,
        message: str = "Account banned",
        code: str = "ACCOUNT_BANNED",
        status_code: int = 403,
        details: list | None = None
    ) -> None:

        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Authorization  (HTTP 403)
# ---------------------------------------------------------------------------

class PermissionDeniedException(PlatformError):
    def __init__(
        self,
        message: str = "Permission denied",
        code: str = "PERMISSION_DENIED",
        status_code: int = 403,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Not Found  (HTTP 404)
# ---------------------------------------------------------------------------

class NotFoundException(PlatformError):
    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        status_code: int = 404,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


class UserNotFoundException(NotFoundException):
    def __init__(
        self,
        message: str = "User not found",
        code: str = "USER_NOT_FOUND",
        status_code: int = 404,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)


# ---------------------------------------------------------------------------
# Validation  (HTTP 422)
# ---------------------------------------------------------------------------

class ValidationException(PlatformError):
    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_FAILED",
        status_code: int = 422,
        details: list | None = None
    ) -> None:
        super().__init__(message, code, status_code, details)



