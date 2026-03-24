"""
Global error handling for the TimeLock API.

Provides centralized exception handlers that return consistent JSON error
responses and log errors for debugging.

Requirements: 13.1, 13.3
"""

from __future__ import annotations

import logging
import traceback

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("timelock.errors")


# ---------------------------------------------------------------------------
# Application-level domain exceptions
# ---------------------------------------------------------------------------

class TimeLockError(Exception):
    """Base exception for all TimeLock domain errors."""

    def __init__(self, detail: str = "An error occurred", status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class NotFoundError(TimeLockError):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(detail=detail, status_code=404)


class AuthenticationError(TimeLockError):
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(detail=detail, status_code=401)


class AuthorizationError(TimeLockError):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(detail=detail, status_code=403)


class ValidationError(TimeLockError):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(detail=detail, status_code=400)


class RateLimitError(TimeLockError):
    def __init__(self, detail: str = "Rate limit exceeded", retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(detail=detail, status_code=429)


# ---------------------------------------------------------------------------
# Error response builder
# ---------------------------------------------------------------------------

def _error_response(
    status_code: int,
    detail: str,
    headers: dict | None = None,
) -> JSONResponse:
    """Build a consistent JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

def _handle_timelock_error(request: Request, exc: TimeLockError) -> JSONResponse:
    """Handle domain-level TimeLock exceptions."""
    logger.warning("Domain error on %s %s: %s", request.method, request.url.path, exc.detail)
    headers = None
    if isinstance(exc, RateLimitError):
        headers = {"Retry-After": str(exc.retry_after)}
    return _error_response(exc.status_code, exc.detail, headers=headers)


def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette/FastAPI HTTP exceptions (401, 403, 404, etc.)."""
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    if exc.status_code >= 500:
        logger.error("HTTP %s on %s %s: %s", exc.status_code, request.method, request.url.path, detail)
    else:
        logger.warning("HTTP %s on %s %s: %s", exc.status_code, request.method, request.url.path, detail)
    return _error_response(exc.status_code, detail)


def _handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic / request validation errors (422 → 400)."""
    errors = exc.errors()
    # Build a human-readable summary
    messages = []
    for err in errors:
        loc = " → ".join(str(l) for l in err.get("loc", []))
        msg = err.get("msg", "invalid")
        messages.append(f"{loc}: {msg}")
    detail = "; ".join(messages) if messages else "Validation failed"
    logger.info("Validation error on %s %s: %s", request.method, request.url.path, detail)
    return _error_response(status.HTTP_400_BAD_REQUEST, detail)


def _handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected server errors."""
    logger.error(
        "Unhandled exception on %s %s: %s\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "An internal server error occurred. Please try again later.",
    )


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_error_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application."""
    app.add_exception_handler(TimeLockError, _handle_timelock_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unhandled_exception)
