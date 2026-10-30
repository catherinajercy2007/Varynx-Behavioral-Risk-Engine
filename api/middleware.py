"""API middleware: Correlation ID propagation, rate limiting, authentication."""
from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from collections.abc import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Propagate or generate X-Correlation-ID on every request/response.

    Satisfies: REQ-012.1
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-API-Version"] = "0.1.0"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter (per-IP).

    Production: use Redis-backed rate limiter.
    Satisfies: REQ-016.6
    """

    def __init__(self, app, requests_per_minute: int = 1000) -> None:
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._counters: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0

        self._counters[client_ip] = [
            t for t in self._counters[client_ip] if t > window_start
        ]

        if len(self._counters[client_ip]) >= self.requests_per_minute:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "status": "error",
                    "error_code": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded: {self.requests_per_minute} req/min",
                },
            )

        self._counters[client_ip].append(now)
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """API-key authentication middleware.

    When *api_key* is set (non-None, non-empty), every request must include an
    ``X-API-Key`` header matching *api_key*.  Requests that fail validation
    receive HTTP 401 with the standard error-response envelope.

    When *api_key* is None or empty, authentication is bypassed and a warning
    is logged once at startup — this preserves local-development compatibility
    without silently disabling security in production.

    Health endpoints (paths in *exempt_paths*) are always accessible without
    authentication so liveness/readiness probes are not blocked.

    Satisfies: REQ-016.3
    """

    def __init__(
        self,
        app,
        api_key: str | None = None,
        exempt_paths: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.api_key = api_key.strip() if api_key else None
        self.exempt_paths = exempt_paths or set()
        self._auth_enabled = bool(self.api_key)
        if not self._auth_enabled:
            logger.warning(
                "VARYNX_API_KEY not set — API authentication is DISABLED. "
                "This is acceptable for local development only; do not deploy "
                "without setting VARYNX_API_KEY."
            )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Health endpoints are always exempt (liveness/readiness probes)
        if request.url.path in self.exempt_paths:
            return await call_next(request)

        # CORS preflight (OPTIONS) must pass without auth headers so browsers
        # can complete the preflight handshake before sending the real request.
        if request.method == "OPTIONS":
            return await call_next(request)

        # If auth is disabled (local dev), allow through
        if not self._auth_enabled:
            return await call_next(request)

        # Auth enabled: validate X-API-Key header
        provided_key = request.headers.get("X-API-Key", "")
        if not provided_key or provided_key.strip() != self.api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "error_code": "UNAUTHORIZED",
                    "message": "Valid X-API-Key header is required.",
                },
                headers={"X-API-Version": "0.1.0"},
            )

        return await call_next(request)