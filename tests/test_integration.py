"""Integration tests for ARGUS WebSocket communication flows.

Tests end-to-end WebSocket message handling including observe and
command flows with mocked Gemini responses.
"""

import base64
import json
import os
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("GEMINI_API_KEY", "test-key-mock")


def _make_valid_screenshot_b64() -> str:
    """Create a valid base64-encoded PNG screenshot for testing.

    Returns:
        Base64-encoded PNG string of a small test image.
    """
    img = Image.new("RGB", (640, 480), color=(50, 50, 50))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.mark.integration
class TestWebSocketIntegration:
    """Integration tests for WebSocket communication flows."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with mocked dependencies."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel") as mock_model_cls, \
             patch("backend.storage.GCS_AVAILABLE", False), \
             patch("backend.storage.GCS_BUCKET", ""):

            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "app_detected": "TestApp",
                "activity_summary": "Testing",
                "errors_seen": None,
                "urls_visited": None,
                "files_open": None,
                "important_context": None,
            })
            mock_instance = MagicMock()
            mock_instance.generate_content.return_value = mock_response
            mock_model_cls.return_value = mock_instance

            from backend.main import app
            yield TestClient(app)

    def test_full_observe_flow(self, client: TestClient) -> None:
        """Test complete observe message flow with valid screenshot."""
        b64 = _make_valid_screenshot_b64()
        with client.websocket_connect("/ws") as ws:
            ws.send_json({
                "type": "observe",
                "screenshot_b64": b64,
            })
            response = json.loads(ws.receive_text())
            assert response["type"] == "observe_ack"
            assert "observation" in response
            assert "app_detected" in response["observation"]
            assert "total_observations" in response

    def test_full_command_flow(self, client: TestClient) -> None:
        """Test complete command message flow."""
        with client.websocket_connect("/ws") as ws:
            # Mock the respond_to_user response
            ws.send_json({
                "type": "command",
                "text": "help me debug",
            })
            response = json.loads(ws.receive_text())
            assert response["type"] == "command_response"

    def test_sequential_observe_then_command(self, client: TestClient) -> None:
        """Test sequential observe followed by command in same session."""
        b64 = _make_valid_screenshot_b64()
        with client.websocket_connect("/ws") as ws:
            # First observe
            ws.send_json({"type": "observe", "screenshot_b64": b64})
            obs_response = json.loads(ws.receive_text())
            assert obs_response["type"] == "observe_ack"

            # Then command
            ws.send_json({"type": "command", "text": "what am I doing?"})
            cmd_response = json.loads(ws.receive_text())
            assert cmd_response["type"] == "command_response"

    def test_rate_limiting_not_triggered_under_limit(self, client: TestClient) -> None:
        """Test that normal usage does not trigger rate limiting."""
        with client.websocket_connect("/ws") as ws:
            for i in range(5):
                ws.send_json({"type": "command", "text": ""})
                response = json.loads(ws.receive_text())
                # Should get command_response errors, not rate limit errors
                assert "Rate limit" not in response.get("error", "")

    def test_mixed_valid_invalid_messages(self, client: TestClient) -> None:
        """Test handling of mixed valid and invalid messages."""
        with client.websocket_connect("/ws") as ws:
            # Invalid JSON
            ws.send_text("not json")
            r1 = json.loads(ws.receive_text())
            assert "error" in r1

            # Unknown type
            ws.send_json({"type": "unknown"})
            r2 = json.loads(ws.receive_text())
            assert "error" in r2

            # Valid empty command (returns error but processed correctly)
            ws.send_json({"type": "command", "text": ""})
            r3 = json.loads(ws.receive_text())
            assert r3.get("type") == "command_response"
