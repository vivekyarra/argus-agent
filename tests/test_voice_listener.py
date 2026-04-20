"""Tests for the VoiceListener client module.

Tests wake word detection, command listening, microphone fallback,
and error handling with mocked speech recognition.
"""

import os
import sys
from unittest.mock import patch, MagicMock
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import client.voice_listener as vl_module
import speech_recognition as sr


class TestVoiceListener:
    """Tests for the VoiceListener class."""

    @patch.object(vl_module.sr, "Microphone")
    @patch.object(vl_module.sr, "Recognizer")
    def test_init_with_microphone(self, mock_recognizer: MagicMock, mock_mic: MagicMock) -> None:
        """Test initialization when microphone is available."""
        from client.voice_listener import VoiceListener
        listener = VoiceListener()
        assert listener.microphone_available is True
        assert listener.wake_word == "argus"

    @patch.object(vl_module.sr, "Microphone", side_effect=OSError("No mic"))
    @patch.object(vl_module.sr, "Recognizer")
    def test_init_without_microphone(self, mock_recognizer: MagicMock, mock_mic: MagicMock) -> None:
        """Test initialization falls back when no microphone found."""
        from client.voice_listener import VoiceListener
        listener = VoiceListener()
        assert listener.microphone_available is False

    @patch.object(vl_module.sr, "Microphone")
    @patch.object(vl_module.sr, "Recognizer")
    def test_wake_word_returns_none_without_mic(self, mock_recognizer: MagicMock, mock_mic: MagicMock) -> None:
        """Test wake word detection returns None without microphone."""
        from client.voice_listener import VoiceListener
        listener = VoiceListener()
        listener.microphone_available = False
        result = listener.listen_for_wake_word()
        assert result is None

    @patch.object(vl_module.sr, "Microphone")
    @patch.object(vl_module.sr, "Recognizer")
    def test_command_fallback_to_keyboard(self, mock_recognizer: MagicMock, mock_mic: MagicMock) -> None:
        """Test command listening falls back to keyboard input."""
        from client.voice_listener import VoiceListener
        listener = VoiceListener()
        listener.microphone_available = False
        with patch("builtins.input", return_value="test command"):
            result = listener.listen_for_command()
        assert result == "test command"

    @patch.object(vl_module.sr, "Microphone")
    @patch.object(vl_module.sr, "Recognizer")
    def test_command_keyboard_eof(self, mock_recognizer: MagicMock, mock_mic: MagicMock) -> None:
        """Test command listening handles EOF gracefully."""
        from client.voice_listener import VoiceListener
        listener = VoiceListener()
        listener.microphone_available = False
        with patch("builtins.input", side_effect=EOFError):
            result = listener.listen_for_command()
        assert result == ""

    @patch.object(vl_module.sr, "Microphone")
    @patch.object(vl_module.sr, "Recognizer")
    def test_custom_wake_word(self, mock_recognizer: MagicMock, mock_mic: MagicMock) -> None:
        """Test custom wake word from environment variable."""
        with patch.dict(os.environ, {"WAKE_WORD": "jarvis"}):
            from client.voice_listener import VoiceListener
            listener = VoiceListener()
            assert listener.wake_word == "jarvis"
