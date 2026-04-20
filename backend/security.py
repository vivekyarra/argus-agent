"""Security utilities for the ARGUS backend.

Provides rate limiting, API key authentication, input sanitization,
and security header middleware for the FastAPI application. All security
controls are configurable via environment variables.

OWASP Top 10 Coverage:
    A03:2021 — Injection: sanitize_command(), validate_url()
    A04:2021 — Insecure Design: RateLimiter
    A05:2021 — Security Misconfiguration: SecurityHeadersMiddleware
    A07:2021 — Identification & Auth Failures: validate_api_key()

Typical usage:
    from backend.security import RateLimiter, validate_api_key, SecurityHeadersMiddleware

    rate_limiter = RateLimiter(requests_per_minute=60)
    app.add_middleware(SecurityHeadersMiddleware)
"""

import hashlib
import hmac
import os
import re
import time
from collections import defaultdict
from typing import Callable, Optional

from fastapi import WebSocket, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RateLimiter:
    """Token-bucket rate limiter scoped per client IP address.

    Mitigates: OWASP A04:2021 — Insecure Design by preventing API abuse
    through configurable per-client request throttling.

    Tracks request timestamps per client and rejects requests that exceed
    the configured rate. Thread-safe for use with async FastAPI handlers.

    Attributes:
        max_requests: Maximum number of requests allowed per window.
        window_seconds: Duration of the rate limiting window in seconds.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        """Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed per window. Defaults to 60.
            window_seconds: Window duration in seconds. Defaults to 60.
        """
        self.max_requests: int = max_requests
        self.window_seconds: int = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, client_id: str) -> None:
        """Remove expired timestamps for a given client.

        Args:
            client_id: Unique identifier for the client (typically IP address).
        """
        cutoff = time.time() - self.window_seconds
        self._requests[client_id] = [
            ts for ts in self._requests[client_id] if ts > cutoff
        ]

    def is_allowed(self, client_id: str) -> bool:
        """Check whether a request from this client is within the rate limit.

        Args:
            client_id: Unique identifier for the client.

        Returns:
            True if the request is allowed, False if rate limit is exceeded.
        """
        self._cleanup(client_id)
        if len(self._requests[client_id]) >= self.max_requests:
            return False
        self._requests[client_id].append(time.time())
        return True

    def get_remaining(self, client_id: str) -> int:
        """Return the number of remaining requests for a client in the current window.

        Args:
            client_id: Unique identifier for the client.

        Returns:
            Number of remaining allowed requests.
        """
        self._cleanup(client_id)
        return max(0, self.max_requests - len(self._requests[client_id]))


def validate_api_key(provided_key: Optional[str]) -> bool:
    """Validate an API key against the configured server key using constant-time comparison.

    Mitigates: OWASP A07:2021 — Identification and Authentication Failures
    by using HMAC-based constant-time comparison to prevent timing attacks.
    If no server key is configured (ARGUS_API_KEY not set), authentication
    is disabled and all requests are allowed.

    Args:
        provided_key: The API key provided by the client.

    Returns:
        True if the key is valid or if authentication is disabled.
    """
    server_key = os.getenv("ARGUS_API_KEY", "")
    if not server_key:
        return True  # Auth disabled if no key configured
    if not provided_key:
        return False
    return hmac.compare_digest(
        hashlib.sha256(provided_key.encode()).digest(),
        hashlib.sha256(server_key.encode()).digest(),
    )


async def authenticate_websocket(websocket: WebSocket) -> bool:
    """Authenticate a WebSocket connection using an API key from query parameters.

    Extracts the ``api_key`` query parameter and validates it against
    the server-configured key.

    Args:
        websocket: The incoming WebSocket connection.

    Returns:
        True if authentication succeeds or if auth is disabled.
    """
    api_key = websocket.query_params.get("api_key")
    return validate_api_key(api_key)


def sanitize_command(command: str, max_length: int = 1000) -> str:
    """Sanitize user command input by stripping control characters and truncating.

    Mitigates: OWASP A03:2021 — Injection by removing null bytes, ANSI
    escape sequences, and other non-printable control characters that
    could be used for command injection or log poisoning. The result
    is truncated to ``max_length`` to prevent buffer overflow attacks.

    Args:
        command: Raw command string from user input.
        max_length: Maximum allowed length for the sanitized output. Defaults to 1000.

    Returns:
        Sanitized and truncated command string.
    """
    if not command:
        return ""
    # Remove null bytes
    command = command.replace("\x00", "")
    # Remove ANSI escape sequences
    command = re.sub(r"\x1b\[[0-9;]*m", "", command)
    # Remove other control characters (keep newlines and tabs)
    command = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", command)
    return command.strip()[:max_length]


def validate_url(url: str) -> bool:
    """Validate that a URL uses an allowed scheme and has proper structure.

    Mitigates: OWASP A03:2021 — Injection and OWASP A10:2021 — SSRF
    by restricting URL schemes to ``http`` and ``https`` only, preventing
    ``file://``, ``javascript:``, ``data:``, and other dangerous URI schemes.

    Args:
        url: The URL string to validate.

    Returns:
        True if the URL is valid and uses an allowed scheme.
    """
    if not url or not isinstance(url, str):
        return False
    allowed_schemes = ("http://", "https://")
    url_lower = url.strip().lower()
    if not any(url_lower.startswith(scheme) for scheme in allowed_schemes):
        return False
    # Basic structure check: scheme + at least a host
    pattern = re.compile(
        r"^https?://"
        r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
        r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
        r"(:\d{1,5})?"
        r"(/.*)?$"
    )
    return bool(pattern.match(url.strip()))


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all HTTP responses.

    Mitigates: OWASP A05:2021 — Security Misconfiguration by setting
    strict Content-Security-Policy with ``strict-dynamic``, X-Frame-Options,
    X-Content-Type-Options, Referrer-Policy, and Permissions-Policy headers.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and add security headers to the response.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response with security headers added.
        """
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'strict-dynamic' 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response
