"""Tests for the Executor client module.

Tests action execution, URL validation, confidence thresholding,
and safe click/type/open_url operations with mocked PyAutoGUI.
"""

import os
import sys
from unittest.mock import patch, MagicMock
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pre-import to resolve the module paths for patching
import client.executor


class TestExecutor:
    """Tests for the Executor class."""

    @patch.object(client.executor, "pyautogui")
    def test_init_enables_failsafe(self, mock_pyautogui: MagicMock) -> None:
        """Test that initialization enables PyAutoGUI failsafe."""
        from client.executor import Executor
        executor = Executor()
        assert mock_pyautogui.FAILSAFE is True

    @patch.object(client.executor, "pyautogui")
    def test_click_success(self, mock_pyautogui: MagicMock) -> None:
        """Test successful click execution."""
        from client.executor import Executor
        executor = Executor()
        result = executor.click(100, 200, narration="Test click")
        assert result is True
        mock_pyautogui.moveTo.assert_called_once()
        mock_pyautogui.click.assert_called_once()

    @patch.object(client.executor, "pyautogui")
    def test_type_text_success(self, mock_pyautogui: MagicMock) -> None:
        """Test successful text typing."""
        from client.executor import Executor
        executor = Executor()
        result = executor.type_text("hello world")
        assert result is True
        mock_pyautogui.write.assert_called_once()

    @patch.object(client.executor, "pyautogui")
    @patch.object(client.executor, "webbrowser")
    def test_open_url_valid_https(self, mock_browser: MagicMock, mock_pyautogui: MagicMock) -> None:
        """Test opening a valid HTTPS URL."""
        from client.executor import Executor
        executor = Executor()
        result = executor.open_url("https://example.com")
        assert result is True
        mock_browser.open.assert_called_once()

    @patch.object(client.executor, "pyautogui")
    @patch.object(client.executor, "webbrowser")
    def test_open_url_blocks_file_scheme(self, mock_browser: MagicMock, mock_pyautogui: MagicMock) -> None:
        """Test that file:// URLs are blocked."""
        from client.executor import Executor
        executor = Executor()
        result = executor.open_url("file:///etc/passwd")
        assert result is False
        mock_browser.open.assert_not_called()

    @patch.object(client.executor, "pyautogui")
    @patch.object(client.executor, "webbrowser")
    def test_open_url_blocks_javascript_scheme(self, mock_browser: MagicMock, mock_pyautogui: MagicMock) -> None:
        """Test that javascript: URLs are blocked."""
        from client.executor import Executor
        executor = Executor()
        result = executor.open_url("javascript:alert(1)")
        assert result is False
        mock_browser.open.assert_not_called()

    @patch.object(client.executor, "pyautogui")
    def test_execute_action_no_action_required(self, mock_pyautogui: MagicMock) -> None:
        """Test execute_action when no action is required."""
        from client.executor import Executor
        executor = Executor()
        result = executor.execute_action({
            "narration": "No action needed",
            "action_required": False,
            "action_type": "none",
        })
        assert result is True

    @patch.object(client.executor, "pyautogui")
    def test_execute_action_low_confidence_skipped(self, mock_pyautogui: MagicMock) -> None:
        """Test that low confidence actions are skipped."""
        from client.executor import Executor
        executor = Executor(min_confidence=0.6)
        result = executor.execute_action({
            "narration": "Uncertain action",
            "action_required": True,
            "action_type": "click",
            "action_target": "button",
            "confidence": 0.3,
            "coordinates": {"found": True, "x": 100, "y": 200},
        })
        assert result is False

    @patch.object(client.executor, "pyautogui")
    def test_execute_action_click_with_coordinates(self, mock_pyautogui: MagicMock) -> None:
        """Test click action execution with valid coordinates."""
        from client.executor import Executor
        executor = Executor()
        result = executor.execute_action({
            "narration": "Clicking button",
            "action_required": True,
            "action_type": "click",
            "action_target": "Submit",
            "confidence": 0.9,
            "coordinates": {"found": True, "x": 300, "y": 400},
        })
        assert result is True

    @patch.object(client.executor, "pyautogui")
    def test_execute_action_click_missing_coordinates(self, mock_pyautogui: MagicMock) -> None:
        """Test click action failure when element not found."""
        from client.executor import Executor
        executor = Executor()
        result = executor.execute_action({
            "narration": "Looking for button",
            "action_required": True,
            "action_type": "click",
            "action_target": "Submit",
            "confidence": 0.9,
            "coordinates": {"found": False, "x": None, "y": None},
        })
        assert result is False
