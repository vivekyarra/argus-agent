"""Gemini API connection test.

Requires a valid GEMINI_API_KEY in the environment. This test is
not included in the standard test suite as it requires live API access.
Run manually: python tests/test_gemini.py
"""

import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("GEMINI_API_KEY", "test-key-mock")


class TestGeminiConnection:
    """Tests for Gemini API connectivity (mocked)."""

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_agent_initializes(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test that GeminiAgent initializes without errors."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        assert agent.model is not None
        mock_configure.assert_called_once()

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_model_name_is_flash_lite(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test that the correct model is configured."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        mock_model.assert_called_once_with("gemini-2.0-flash-lite")
