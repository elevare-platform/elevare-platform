"""Custom Starlette middleware for the Elevare Platform

Currently provides:
- ``RequestLoggingMiddleware``: logs every inbound request and its
  completed response, attaching a unique ``X-Request-ID`` header for
  distributed tracing.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
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

