"""
app/middleware/request_logging.py

Request logging middleware for Praxis AI.

For every HTTP request this middleware:
  1. Generates (or propagates) an X-Request-ID header.
  2. Sets that ID into the logging context var so all log lines
     emitted during the request automatically carry it.
  3. Logs the method, path, status, and elapsed time at INFO level.
  4. Returns the X-Request-ID header in the response so clients can
     correlate their own traces.

SSE / streaming endpoints: the timing reflects time-to-first-byte only
because the response object is returned before the stream completes.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.utils.logging import set_request_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Lightweight request/response logger with request-ID propagation.

    Skips /health and /metrics paths to avoid log noise from load-balancer
    health checks on EC2.
    """

    _SKIP_PATHS = frozenset({"/health", "/metrics", "/favicon.ico"})

    async def dispatch(self, request: Request, call_next) -> Response:
        # Propagate or generate request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
        set_request_id(request_id)

        skip = request.url.path in self._SKIP_PATHS

        if not skip:
            logger.info(
                "→ %s %s",
                request.method,
                request.url.path,
            )

        start = time.perf_counter()
        try:
            response: Response = await call_next(request)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "✗ %s %s — EXCEPTION after %.1f ms: %s",
                request.method,
                request.url.path,
                elapsed,
                exc,
                exc_info=True,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000

        if not skip:
            level = logging.WARNING if response.status_code >= 400 else logging.INFO
            logger.log(
                level,
                "← %s %s %d (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed,
            )

        # Always return request ID in response headers
        response.headers["X-Request-ID"] = request_id
        return response
