"""Property-based tests for ARGUS using Hypothesis.

Generates randomized edge-case inputs to verify that security
controls, sanitization functions, and validation logic never crash
regardless of input shape or content.

Uses the ``hypothesis`` library for property-based testing with
configurable strategies.
"""

import os
import sys
from typing import Any

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.security import sanitize_command, validate_url, validate_api_key, RateLimiter


class TestSanitizeCommandProperties:
    """Property-based tests for command sanitization."""

    @given(text=st.text(min_size=0, max_size=5000))
    @settings(max_examples=200)
    def test_never_crashes(self, text: str) -> None:
        """Sanitize must never raise on any string input."""
        result: str = sanitize_command(text)
        assert isinstance(result, str)

    @given(text=st.text(min_size=0, max_size=5000))
    @settings(max_examples=200)
    def test_output_never_exceeds_max_length(self, text: str) -> None:
        """Output length must never exceed the configured max."""
        result: str = sanitize_command(text, max_length=100)
        assert len(result) <= 100

    @given(text=st.text(min_size=0, max_size=5000))
    @settings(max_examples=200)
    def test_no_null_bytes_in_output(self, text: str) -> None:
        """Output must never contain null bytes."""
        result: str = sanitize_command(text)
        assert "\x00" not in result

    @given(text=st.text(min_size=1, max_size=100, alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
    )))
    @settings(max_examples=100)
    def test_printable_input_preserved(self, text: str) -> None:
        """Printable characters should survive sanitization."""
        result: str = sanitize_command(text)
        assert len(result) > 0 or text.strip() == ""


class TestURLValidationProperties:
    """Property-based tests for URL validation."""

    @given(text=st.text(min_size=0, max_size=2000))
    @settings(max_examples=200)
    def test_never_crashes(self, text: str) -> None:
        """URL validation must never raise on any string input."""
        result: bool = validate_url(text)
        assert isinstance(result, bool)

    @given(scheme=st.sampled_from([
        "file://", "ftp://", "javascript:", "data:", "vbscript:",
        "blob:", "about:", "chrome://", "ssh://", "telnet://",
    ]))
    @settings(max_examples=50)
    def test_dangerous_schemes_always_blocked(self, scheme: str) -> None:
        """Non-http(s) schemes must always be rejected."""
        url: str = f"{scheme}evil.com/malware"
        assert validate_url(url) is False

    @given(host=st.from_regex(r"[a-z][a-z0-9]{0,20}(\.[a-z][a-z0-9]{0,10}){0,3}", fullmatch=True))
    @settings(max_examples=100)
    def test_valid_http_urls_accepted(self, host: str) -> None:
        """Well-formed HTTP URLs must be accepted."""
        assume(len(host) >= 1)
        url: str = f"http://{host}"
        assert validate_url(url) is True


class TestRateLimiterProperties:
    """Property-based tests for rate limiter."""

    @given(
        max_reqs=st.integers(min_value=1, max_value=100),
        num_requests=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100)
    def test_never_allows_more_than_max(self, max_reqs: int, num_requests: int) -> None:
        """Rate limiter must never allow more than max_requests."""
        limiter = RateLimiter(max_requests=max_reqs, window_seconds=3600)
        allowed: int = sum(1 for _ in range(num_requests) if limiter.is_allowed("test"))
        assert allowed <= max_reqs

    @given(client_id=st.text(min_size=1, max_size=50))
    @settings(max_examples=50)
    def test_first_request_always_allowed(self, client_id: str) -> None:
        """First request from any client must always be allowed."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter.is_allowed(client_id) is True


class TestAPIKeyProperties:
    """Property-based tests for API key validation."""

    @given(key=st.text(min_size=0, max_size=500))
    @settings(max_examples=100)
    def test_never_crashes(self, key: str) -> None:
        """API key validation must never raise on any input."""
        result: bool = validate_api_key(key)
        assert isinstance(result, bool)
