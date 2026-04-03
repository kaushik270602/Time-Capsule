"""
CSRF protection middleware for FastAPI.

Implements double-submit cookie pattern:
1. Server sets a CSRF token cookie on every response.
2. State-changing requests (POST/PUT/PATCH/DELETE) must include
   the same token in the X-CSRF-Token header.
3. Safe methods (GET/HEAD/OPTIONS) and whitelisted paths are exempt.

Requirements: 15.3
"""

from __future__ import annotations

import secrets
from typing import Callable

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_TOKEN_LENGTH = 32

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths that are exempt from CSRF checks (e.g. API-only auth endpoints
# that rely on Bearer tokens rather than cookies for auth).
EXEMPT_PATHS: frozenset[str] = frozenset({
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/verify-email",
    "/api/auth/password-reset-request",
    "/api/auth/password-reset",
    "/health",
    "/",
})


def _generate_csrf_token() -> str:
    return secrets.token_hex(CSRF_TOKEN_LENGTH)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection.

    On every response a csrf_token cookie is set (or refreshed).
    State-changing requests must echo the cookie value in the
    X-CSRF-Token header.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from app.config import settings

        method = request.method.upper()
        path = request.url.path

        # Disable CSRF protection in debug/development mode
        if settings.DEBUG:
            response = await call_next(request)
            self._ensure_csrf_cookie(request, response)
            return response

        # Always let safe methods and exempt paths through
        if method in SAFE_METHODS or path in EXEMPT_PATHS:
            response = await call_next(request)
            self._ensure_csrf_cookie(request, response)
            return response

        # For state-changing methods, validate the CSRF token
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        header_token = request.headers.get(CSRF_HEADER_NAME)

        if not cookie_token or not header_token or cookie_token != header_token:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token missing or invalid"},
            )

        response = await call_next(request)
        self._ensure_csrf_cookie(request, response)
        return response

    @staticmethod
    def _ensure_csrf_cookie(request: Request, response: Response) -> None:
        """Set or refresh the CSRF cookie if not already present."""
        existing = request.cookies.get(CSRF_COOKIE_NAME)
        token = existing or _generate_csrf_token()
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            httponly=False,  # JS needs to read this to set the header
            samesite="lax",
            secure=False,  # Set True in production with HTTPS
            path="/",
        )
