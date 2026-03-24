"""
Security headers middleware for FastAPI.

Adds standard security headers to all responses and optionally
redirects HTTP → HTTPS in production.

Requirements: 15.2
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects security headers into every response:
    - Strict-Transport-Security (HSTS)
    - Content-Security-Policy (CSP)
    - X-Frame-Options
    - X-Content-Type-Options
    - X-XSS-Protection
    - Referrer-Policy
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # HSTS – only meaningful over HTTPS, but we always set it so
        # the header is present the moment the app sits behind TLS.
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Redirects HTTP requests to HTTPS in production (when DEBUG is False).

    In development / debug mode the middleware is a no-op so local HTTP
    workflows are unaffected.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not settings.DEBUG and request.url.scheme == "http":
            url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(url), status_code=301)

        return await call_next(request)
