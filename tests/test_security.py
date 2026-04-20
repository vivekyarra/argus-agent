"""Security-focused tests for ARGUS.

Tests rate limiting, API key validation, input sanitization, URL
validation, and security header middleware.
"""

import os
import time
from unittest.mock import patch

import pytest

from backend.security import (
    RateLimiter,
    validate_api_key,
    sanitize_command,
    validate_url,
    SecurityHeadersMiddleware,
)


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allows_requests_within_limit(self) -> None:
        """Test that requests within the limit are allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert limiter.is_allowed("client1") is True

    def test_blocks_requests_exceeding_limit(self) -> None:
        """Test that requests exceeding the limit are blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False

    def test_separate_clients_have_separate_limits(self) -> None:
        """Test that different clients have independent rate limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False
        # Different client should still be allowed
        assert limiter.is_allowed("client2") is True

    def test_get_remaining_requests(self) -> None:
        """Test remaining request count calculation."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        assert limiter.get_remaining("client1") == 5
        limiter.is_allowed("client1")
        assert limiter.get_remaining("client1") == 4

    def test_window_expiry_allows_new_requests(self) -> None:
        """Test that expired window entries are cleaned up."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        assert limiter.is_allowed("client1") is True
        assert limiter.is_allowed("client1") is False
        time.sleep(1.1)
        assert limiter.is_allowed("client1") is True


class TestAPIKeyValidation:
    """Tests for API key validation."""

    def test_no_server_key_allows_all(self) -> None:
        """Test that missing server key disables authentication."""
        with patch.dict(os.environ, {"ARGUS_API_KEY": ""}):
            assert validate_api_key(None) is True
            assert validate_api_key("anything") is True

    def test_valid_key_accepted(self) -> None:
        """Test that correct API key is accepted."""
        with patch.dict(os.environ, {"ARGUS_API_KEY": "secret123"}):
            assert validate_api_key("secret123") is True

    def test_invalid_key_rejected(self) -> None:
        """Test that incorrect API key is rejected."""
        with patch.dict(os.environ, {"ARGUS_API_KEY": "secret123"}):
            assert validate_api_key("wrong_key") is False

    def test_empty_key_rejected_when_configured(self) -> None:
        """Test that empty key is rejected when server key is set."""
        with patch.dict(os.environ, {"ARGUS_API_KEY": "secret123"}):
            assert validate_api_key("") is False
            assert validate_api_key(None) is False


class TestCommandSanitization:
    """Tests for command input sanitization."""

    def test_normal_command_passes_through(self) -> None:
        """Test that normal commands are not modified."""
        assert sanitize_command("help me debug") == "help me debug"

    def test_null_bytes_removed(self) -> None:
        """Test that null bytes are stripped from commands."""
        assert sanitize_command("hello\x00world") == "helloworld"

    def test_empty_command_returns_empty(self) -> None:
        """Test that empty input returns empty string."""
        assert sanitize_command("") == ""
        assert sanitize_command(None) == ""

    def test_command_truncation(self) -> None:
        """Test that long commands are truncated."""
        long_cmd = "a" * 2000
        result = sanitize_command(long_cmd, max_length=100)
        assert len(result) == 100

    def test_ansi_escape_removal(self) -> None:
        """Test that ANSI escape sequences are removed."""
        result = sanitize_command("hello\x1b[31mworld\x1b[0m")
        assert "\x1b" not in result

    def test_whitespace_stripping(self) -> None:
        """Test that leading/trailing whitespace is stripped."""
        assert sanitize_command("  hello world  ") == "hello world"


class TestURLValidation:
    """Tests for URL validation."""

    def test_valid_http_url(self) -> None:
        """Test that valid HTTP URLs are accepted."""
        assert validate_url("http://example.com") is True

    def test_valid_https_url(self) -> None:
        """Test that valid HTTPS URLs are accepted."""
        assert validate_url("https://example.com/path") is True

    def test_file_scheme_rejected(self) -> None:
        """Test that file:// scheme is rejected."""
        assert validate_url("file:///etc/passwd") is False

    def test_javascript_scheme_rejected(self) -> None:
        """Test that javascript: scheme is rejected."""
        assert validate_url("javascript:alert(1)") is False

    def test_empty_url_rejected(self) -> None:
        """Test that empty URLs are rejected."""
        assert validate_url("") is False
        assert validate_url(None) is False

    def test_url_with_port(self) -> None:
        """Test that URLs with port numbers are accepted."""
        assert validate_url("http://localhost:8000") is True

    def test_url_with_path(self) -> None:
        """Test that URLs with paths are accepted."""
        assert validate_url("https://example.com/api/v1/data") is True
