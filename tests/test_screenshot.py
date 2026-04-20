"""Tests for the ScreenCapture client module.

Tests screen capture, base64 encoding, and pixel-diff change detection
with mocked MSS instances.
"""

import base64
import os
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock
from typing import Any

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client.screen_capture as sc_module


def _make_b64_image(color: tuple = (30, 30, 30), size: tuple = (100, 100)) -> str:
    """Create a base64-encoded PNG image.

    Args:
        color: RGB color tuple.
        size: Image dimensions (width, height).

    Returns:
        Base64-encoded PNG string.
    """
    img = Image.new("RGB", size, color=color)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


class TestScreenCapture:
    """Tests for the ScreenCapture class."""

    @patch.object(sc_module.mss, "mss")
    def test_init(self, mock_mss: MagicMock) -> None:
        """Test successful initialization."""
        from client.screen_capture import ScreenCapture
        sc = ScreenCapture()
        assert sc.last_screenshot_b64 is None
        assert sc.sct is not None

    @patch.object(sc_module.mss, "mss")
    def test_has_significant_change_first_capture(self, mock_mss: MagicMock) -> None:
        """Test that first capture always returns True."""
        from client.screen_capture import ScreenCapture
        sc = ScreenCapture()
        b64 = _make_b64_image()
        assert sc.has_significant_change(b64) is True

    @patch.object(sc_module.mss, "mss")
    def test_no_change_below_threshold(self, mock_mss: MagicMock) -> None:
        """Test that identical frames are below threshold."""
        from client.screen_capture import ScreenCapture
        sc = ScreenCapture()
        b64 = _make_b64_image((30, 30, 30))
        sc.has_significant_change(b64)  # First capture
        assert sc.has_significant_change(b64, threshold_percent=15.0) is False

    @patch.object(sc_module.mss, "mss")
    def test_significant_change_detected(self, mock_mss: MagicMock) -> None:
        """Test that dramatically different frames are detected as changed."""
        from client.screen_capture import ScreenCapture
        sc = ScreenCapture()
        b64_dark = _make_b64_image((0, 0, 0))
        b64_bright = _make_b64_image((255, 255, 255))
        sc.has_significant_change(b64_dark)  # Set baseline
        assert sc.has_significant_change(b64_bright, threshold_percent=15.0) is True

    @patch.object(sc_module.mss, "mss")
    def test_shape_mismatch_returns_true(self, mock_mss: MagicMock) -> None:
        """Test that resolution changes are detected as significant."""
        from client.screen_capture import ScreenCapture
        sc = ScreenCapture()
        b64_small = _make_b64_image(size=(100, 100))
        b64_large = _make_b64_image(size=(200, 200))
        sc.has_significant_change(b64_small)  # Set baseline
        assert sc.has_significant_change(b64_large) is True

    @patch.object(sc_module.mss, "mss")
    def test_invalid_b64_returns_true(self, mock_mss: MagicMock) -> None:
        """Test that invalid base64 data triggers capture (safe fallback)."""
        from client.screen_capture import ScreenCapture
        sc = ScreenCapture()
        b64 = _make_b64_image()
        sc.has_significant_change(b64)  # Set baseline
        # Corrupt the stored b64
        sc.last_screenshot_b64 = "invalid_data"
        assert sc.has_significant_change(b64) is True
