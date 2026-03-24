"""Tests for security headers and HTTPS redirect middleware."""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from app.middleware.security_headers import SecurityHeadersMiddleware, HTTPSRedirectMiddleware


def _make_app(*middlewares) -> FastAPI:
    """Create a minimal FastAPI app with the given middleware."""
    app = FastAPI()
    for mw in middlewares:
        app.add_middleware(mw)

    @app.get("/test")
    async def _test():
        return {"ok": True}

    return app


# ---------- SecurityHeadersMiddleware ----------

class TestSecurityHeaders:
    def setup_method(self):
        self.app = _make_app(SecurityHeadersMiddleware)
        self.client = TestClient(self.app)

    def test_hsts_header_present(self):
        resp = self.client.get("/test")
        assert "strict-transport-security" in resp.headers
        assert "max-age=31536000" in resp.headers["strict-transport-security"]
        assert "includeSubDomains" in resp.headers["strict-transport-security"]

    def test_csp_header_present(self):
        resp = self.client.get("/test")
        csp = resp.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_x_frame_options_deny(self):
        resp = self.client.get("/test")
        assert resp.headers["x-frame-options"] == "DENY"

    def test_x_content_type_options(self):
        resp = self.client.get("/test")
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_x_xss_protection(self):
        resp = self.client.get("/test")
        assert resp.headers["x-xss-protection"] == "1; mode=block"

    def test_referrer_policy(self):
        resp = self.client.get("/test")
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"


# ---------- HTTPSRedirectMiddleware ----------

class TestHTTPSRedirect:
    def test_no_redirect_in_debug_mode(self):
        """In debug mode (default), HTTP requests pass through."""
        with patch("app.middleware.security_headers.settings") as mock_settings:
            mock_settings.DEBUG = True
            app = _make_app(HTTPSRedirectMiddleware)
            client = TestClient(app)
            resp = client.get("/test")
            assert resp.status_code == 200

    def test_redirect_in_production(self):
        """When DEBUG=False, HTTP requests get a 301 redirect to HTTPS."""
        with patch("app.middleware.security_headers.settings") as mock_settings:
            mock_settings.DEBUG = False
            app = _make_app(HTTPSRedirectMiddleware)
            client = TestClient(app, base_url="http://testserver")
            resp = client.get("/test", follow_redirects=False)
            assert resp.status_code == 301
            assert resp.headers["location"].startswith("https://")
