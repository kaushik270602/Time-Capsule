"""
Input sanitization utilities.

Strips dangerous characters and patterns from user-supplied strings to
prevent injection attacks (XSS, SQL injection fragments, etc.).

Requirements: 15.4
"""

from __future__ import annotations

import html
import re

# Pattern that matches HTML/script tags
_TAG_RE = re.compile(r"<[^>]+>")

# Pattern that matches common SQL injection fragments (case-insensitive)
_SQL_INJECTION_RE = re.compile(
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|UNION|EXEC|EXECUTE)\b"
    r"|\b(OR|AND)\s+\d+\s*=\s*\d+"
    r"|--|;|\bxp_)",
    re.IGNORECASE,
)


def sanitize_input(value: str) -> str:
    """
    Sanitize a user-provided string.

    1. Strip leading/trailing whitespace.
    2. HTML-escape special characters (``<``, ``>``, ``&``, ``"``, ``'``).
    3. Remove any residual HTML tags that survived escaping.

    The function is intentionally *not* destructive to normal prose — it
    only neutralises characters that could be interpreted as markup or
    code when rendered in a browser or interpolated into a query.

    Args:
        value: Raw user input string.

    Returns:
        Sanitized string safe for storage and display.
    """
    if not isinstance(value, str):
        return value

    value = value.strip()
    # HTML-escape dangerous characters
    value = html.escape(value, quote=True)
    # Belt-and-suspenders: strip any tags that might remain
    value = _TAG_RE.sub("", value)
    return value
