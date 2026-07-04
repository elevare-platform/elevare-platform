"""Custom Starlette middleware for the Elevare Platform

Currently provides:
- ``RequestLoggingMiddleware``: logs every inbound request and its
  completed response, attaching a unique ``X-Request-ID`` header for
  distributed tracing.
- ``SecurityHeadersMiddleware``: adds HTTP security headers to every
  response to protect against common web vulnerabilities.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add HTTP security headers to every response.

    Headers applied:
    - X-Content-Type-Options: prevents MIME-type sniffing
    - X-Frame-Options: prevents clickjacking via iframes
    - X-XSS-Protection: legacy XSS filter for older browsers
    - Referrer-Policy: limits referrer info sent to third parties
    - Permissions-Policy: disables browser features not needed by this API
    - Strict-Transport-Security: enforces HTTPS (only set when not in debug mode)
    - Content-Security-Policy: restricts resource loading for API responses
    """

    def __init__(self, app, debug: bool = False) -> None:
        """Initialise middleware with debug flag to control HSTS header."""
        super().__init__(app)
        self._debug = debug

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add security headers to every response."""
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'"
        )

        # HSTS — only over HTTPS, not in local dev
        if not self._debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        # Remove server banner to avoid version disclosure
        if "server" in response.headers:
            del response.headers["server"]

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every inbound request and its completed response with a request ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Log request start, call the next handler, then log completion or failure."""
        # Skip logging for CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        logger.info(
            "Request started | request_id=%s method=%s path=%s client_ip=%s",
            request_id,
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown"
        )

        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                "Request failed | request_id=%s duration_ms=%.2f",
                request_id,
                process_time,
                exc_info=True
            )

            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": [],
                },
                headers={"X-Request-ID": request_id}
            )

        response.headers["X-Request-ID"] = request_id

        process_time = (time.time() - start_time) * 1000
        logger.info(
            "Request completed | request_id=%s status_code=%s duration_ms=%.2f",
            request_id,
            response.status_code,
            process_time,
        )

        return response

