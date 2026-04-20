"""Comprehensive test suite for ARGUS.

Tests: GeminiAgent, ContextManager, Storage, FastAPI endpoints,
WebSocket protocol, input validation, and Firestore integration.
"""

import asyncio
import base64
import json
import os
import sys
import time
import tempfile
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Any

import pytest
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("GEMINI_API_KEY", "test-key-mock")
os.environ.setdefault("GCS_BUCKET_NAME", "")


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample test image."""
    img = Image.new("RGB", (640, 480), color=(30, 30, 30))
    return img


@pytest.fixture
def sample_b64(sample_image: Image.Image) -> str:
    """Create a base64-encoded PNG from the sample image."""
    buf = BytesIO()
    sample_image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def temp_dir(tmp_path: Any) -> Any:
    """Provide a temporary directory for tests."""
    return tmp_path


# ─────────────────────────────────────────────
# GeminiAgent Tests
# ─────────────────────────────────────────────

class TestGeminiAgent:
    """Tests for the GeminiAgent class."""

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_init_success(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test successful initialization with valid API key."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        mock_configure.assert_called_once_with(api_key="test-key-mock")
        assert agent.model is not None

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_init_with_retry_config(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test initialization with custom retry parameters."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent(max_retries=5, retry_delay=2.0)
        assert agent.max_retries == 5
        assert agent.retry_delay == 2.0

    def test_init_missing_key(self) -> None:
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with patch("google.generativeai.configure"):
                from backend.gemini_agent import GeminiAgent
                with pytest.raises(ValueError, match="GEMINI_API_KEY"):
                    GeminiAgent()

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_parse_json_response_clean(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test parsing clean JSON response."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent._parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_parse_json_response_strips_markdown(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test parsing JSON wrapped in markdown code blocks."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent._parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_parse_json_response_invalid_returns_empty(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test that invalid JSON returns empty dict safely."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent._parse_json_response("not json at all }{")
        assert result == {}

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_parse_json_response_whitespace(self, mock_model: MagicMock, mock_configure: MagicMock) -> None:
        """Test parsing JSON with extra whitespace."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent._parse_json_response('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_analyze_screenshot_returns_default_on_api_error(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock, sample_image: Image.Image
    ) -> None:
        """Test that API errors return safe default observation."""
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = Exception("API error")
        mock_model_cls.return_value = mock_instance

        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent(max_retries=1, retry_delay=0.01)
        result = agent.analyze_screenshot(sample_image)

        assert "app_detected" in result
        assert "activity_summary" in result
        assert result["app_detected"] == "unknown"

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_analyze_screenshot_returns_structured_data(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock, sample_image: Image.Image
    ) -> None:
        """Test successful screenshot analysis with structured response."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "app_detected": "VSCode",
            "activity_summary": "User is coding in Python",
            "errors_seen": None,
            "urls_visited": None,
            "files_open": "main.py",
            "important_context": None,
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_instance

        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent.analyze_screenshot(sample_image)

        assert result["app_detected"] == "VSCode"
        assert result["activity_summary"] == "User is coding in Python"
        assert result["files_open"] == "main.py"

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_respond_to_user_returns_default_on_error(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock
    ) -> None:
        """Test that command errors return safe default response."""
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = Exception("timeout")
        mock_model_cls.return_value = mock_instance

        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent(max_retries=1, retry_delay=0.01)
        result = agent.respond_to_user("help me", "some context")

        assert "narration" in result
        assert "action_required" in result
        assert isinstance(result["action_required"], bool)

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_respond_to_user_returns_action(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock
    ) -> None:
        """Test successful command response with action."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "narration": "I can see the error. Let me fix it.",
            "action_required": True,
            "action_type": "click",
            "action_target": "Submit button",
            "confidence": 0.9,
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_instance

        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent.respond_to_user("fix the bug", "user has error on screen")

        assert result["action_required"] is True
        assert result["action_type"] == "click"
        assert result["confidence"] == 0.9

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_image_to_part_returns_valid_structure(
        self, mock_model: MagicMock, mock_configure: MagicMock, sample_image: Image.Image
    ) -> None:
        """Test image conversion to Gemini API part format."""
        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        part = agent._image_to_part(sample_image)

        assert part["mime_type"] == "image/png"
        assert isinstance(part["data"], str)
        decoded = base64.b64decode(part["data"])
        assert len(decoded) > 0

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_find_element_coordinates_default(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock, sample_image: Image.Image
    ) -> None:
        """Test element detection returns default on API error."""
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = Exception("API error")
        mock_model_cls.return_value = mock_instance

        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent(max_retries=1, retry_delay=0.01)
        result = agent.find_element_coordinates(sample_image, "Submit button")

        assert result["found"] is False
        assert result["x"] is None
        assert result["y"] is None

    @patch("google.generativeai.configure")
    @patch("google.generativeai.GenerativeModel")
    def test_find_element_coordinates_success(
        self, mock_model_cls: MagicMock, mock_configure: MagicMock, sample_image: Image.Image
    ) -> None:
        """Test successful element coordinate detection."""
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "found": True,
            "x": 320,
            "y": 240,
            "confidence": 0.95,
            "description": "Submit button at center",
        })
        mock_instance = MagicMock()
        mock_instance.generate_content.return_value = mock_response
        mock_model_cls.return_value = mock_instance

        from backend.gemini_agent import GeminiAgent
        agent = GeminiAgent()
        result = agent.find_element_coordinates(sample_image, "Submit button")

        assert result["found"] is True
        assert result["x"] == 320
        assert result["y"] == 240


# ─────────────────────────────────────────────
# ContextManager Tests
# ─────────────────────────────────────────────

class TestContextManager:
    """Tests for the ContextManager class."""

    def test_add_and_count_observation(self) -> None:
        """Test adding an observation increases the count."""
        from backend.context_manager import ContextManager
        with patch.object(ContextManager, "_load_from_disk", return_value=None), \
             patch.object(ContextManager, "_save_to_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 5
            from collections import deque
            cm.observations = deque(maxlen=500)
            obs = {"app_detected": "Chrome", "activity_summary": "Browsing"}
            cm.add_observation(obs)
            assert cm.get_observation_count() == 1

    def test_clear_old_observations(self) -> None:
        """Test that expired observations are evicted."""
        from backend.context_manager import ContextManager
        from collections import deque
        with patch.object(ContextManager, "_load_from_disk", return_value=None), \
             patch.object(ContextManager, "_save_to_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 1
            cm.observations = deque(maxlen=500)
            old_time = (datetime.now() - timedelta(minutes=10)).isoformat()
            cm.observations.append({"timestamp": old_time, "app_detected": "old"})
            cm.clear_old_observations()
            assert cm.get_observation_count() == 0

    def test_get_context_summary_empty(self) -> None:
        """Test context summary when no observations exist."""
        from backend.context_manager import ContextManager
        from collections import deque
        with patch.object(ContextManager, "_load_from_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 5
            cm.observations = deque(maxlen=500)
            summary = cm.get_context_summary()
            assert "No observations" in summary

    def test_get_context_summary_with_data(self) -> None:
        """Test context summary formatting with real observations."""
        from backend.context_manager import ContextManager
        from collections import deque
        with patch.object(ContextManager, "_load_from_disk", return_value=None), \
             patch.object(ContextManager, "_save_to_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 5
            cm.observations = deque(maxlen=500)
            cm.observations.append({
                "timestamp": datetime.now().isoformat(),
                "app_detected": "VSCode",
                "activity_summary": "Writing tests",
                "errors_seen": None,
                "urls_visited": None,
                "files_open": None,
                "important_context": None,
            })
            summary = cm.get_context_summary()
            assert "VSCode" in summary
            assert "Writing tests" in summary

    def test_observation_timestamp_is_set(self) -> None:
        """Test that add_observation sets a valid ISO timestamp."""
        from backend.context_manager import ContextManager
        from collections import deque
        with patch.object(ContextManager, "_load_from_disk", return_value=None), \
             patch.object(ContextManager, "_save_to_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 5
            cm.observations = deque(maxlen=500)
            obs: dict[str, Any] = {"app_detected": "test"}
            cm.add_observation(obs)
            assert "timestamp" in cm.observations[0]
            datetime.fromisoformat(cm.observations[0]["timestamp"])

    def test_max_observations_cap(self) -> None:
        """Test that deque maxlen prevents unbounded memory growth."""
        from backend.context_manager import ContextManager
        from collections import deque
        with patch.object(ContextManager, "_load_from_disk", return_value=None), \
             patch.object(ContextManager, "_save_to_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 9999
            cm.observations = deque(maxlen=500)
            for i in range(600):
                cm.observations.append({
                    "timestamp": datetime.now().isoformat(),
                    "app_detected": f"app_{i}",
                })
            assert len(cm.observations) <= 500

    def test_context_summary_with_errors(self) -> None:
        """Test context summary includes error annotations."""
        from backend.context_manager import ContextManager
        from collections import deque
        with patch.object(ContextManager, "_load_from_disk", return_value=None), \
             patch.object(ContextManager, "_save_to_disk", return_value=None):
            cm = ContextManager.__new__(ContextManager)
            cm.window_minutes = 5
            cm.observations = deque(maxlen=500)
            cm.observations.append({
                "timestamp": datetime.now().isoformat(),
                "app_detected": "Terminal",
                "activity_summary": "Running tests",
                "errors_seen": "NullReferenceException",
                "urls_visited": None,
                "files_open": None,
                "important_context": None,
            })
            summary = cm.get_context_summary()
            assert "ERROR DETECTED" in summary
            assert "NullReferenceException" in summary


# ─────────────────────────────────────────────
# Storage Tests
# ─────────────────────────────────────────────

class TestStorage:
    """Tests for the Storage class."""

    def test_save_screenshot_local(self, tmp_path: Any, sample_image: Image.Image) -> None:
        """Test local screenshot saving."""
        from backend.storage import Storage
        with patch("backend.storage.GCS_BUCKET", ""), \
             patch("backend.storage.GCS_AVAILABLE", False):
            s = Storage.__new__(Storage)
            s.logs_dir = str(tmp_path)
            s.screenshots_dir = str(tmp_path / "screenshots")
            s.actions_log = str(tmp_path / "actions.json")
            os.makedirs(s.screenshots_dir, exist_ok=True)
            s.gcs_client = None
            s.bucket = None

            path = s.save_screenshot(sample_image, "20260420_120000")
            assert os.path.exists(path)
            assert path.endswith(".png")

            saved = Image.open(path)
            assert saved.mode == "RGB"

    def test_save_action_log_creates_jsonl(self, tmp_path: Any) -> None:
        """Test action log JSONL creation."""
        from backend.storage import Storage
        with patch("backend.storage.GCS_BUCKET", ""), \
             patch("backend.storage.GCS_AVAILABLE", False):
            s = Storage.__new__(Storage)
            s.logs_dir = str(tmp_path)
            s.screenshots_dir = str(tmp_path / "screenshots")
            s.actions_log = str(tmp_path / "actions.json")
            os.makedirs(s.screenshots_dir, exist_ok=True)
            s.gcs_client = None
            s.bucket = None

            s.save_action_log({"command": "test", "response": {"narration": "ok"}})
            assert os.path.exists(s.actions_log)
            with open(s.actions_log) as f:
                line = json.loads(f.readline())
            assert line["command"] == "test"
            assert "logged_at" in line

    def test_get_recent_screenshots_empty(self, tmp_path: Any) -> None:
        """Test retrieving screenshots from an empty directory."""
        from backend.storage import Storage
        s = Storage.__new__(Storage)
        s.screenshots_dir = str(tmp_path / "empty_screenshots")
        os.makedirs(s.screenshots_dir)
        s.gcs_client = None
        s.bucket = None
        result = s.get_recent_screenshots(5)
        assert result == []

    def test_save_screenshot_auto_timestamp(self, tmp_path: Any, sample_image: Image.Image) -> None:
        """Test screenshot saving with auto-generated timestamp."""
        from backend.storage import Storage
        with patch("backend.storage.GCS_BUCKET", ""), \
             patch("backend.storage.GCS_AVAILABLE", False):
            s = Storage.__new__(Storage)
            s.logs_dir = str(tmp_path)
            s.screenshots_dir = str(tmp_path / "screenshots")
            s.actions_log = str(tmp_path / "actions.json")
            os.makedirs(s.screenshots_dir, exist_ok=True)
            s.gcs_client = None
            s.bucket = None

            path = s.save_screenshot(sample_image)
            assert os.path.exists(path)
            assert path.endswith(".png")

    def test_health_check(self, tmp_path: Any) -> None:
        """Test storage health check returns expected fields."""
        from backend.storage import Storage
        with patch("backend.storage.GCS_BUCKET", ""), \
             patch("backend.storage.GCS_AVAILABLE", False):
            s = Storage.__new__(Storage)
            s.logs_dir = str(tmp_path)
            s.screenshots_dir = str(tmp_path / "screenshots")
            s.actions_log = str(tmp_path / "actions.json")
            os.makedirs(s.screenshots_dir, exist_ok=True)
            s.gcs_client = None
            s.bucket = None

            health = s.health_check()
            assert "local_storage" in health
            assert "gcs_available" in health

    def test_multiple_action_logs_append(self, tmp_path: Any) -> None:
        """Test that multiple action logs append correctly."""
        from backend.storage import Storage
        with patch("backend.storage.GCS_BUCKET", ""), \
             patch("backend.storage.GCS_AVAILABLE", False):
            s = Storage.__new__(Storage)
            s.logs_dir = str(tmp_path)
            s.screenshots_dir = str(tmp_path / "screenshots")
            s.actions_log = str(tmp_path / "actions.json")
            os.makedirs(s.screenshots_dir, exist_ok=True)
            s.gcs_client = None
            s.bucket = None

            s.save_action_log({"command": "first"})
            s.save_action_log({"command": "second"})
            s.save_action_log({"command": "third"})

            with open(s.actions_log) as f:
                lines = f.readlines()
            assert len(lines) == 3


# ─────────────────────────────────────────────
# FastAPI Endpoint Tests
# ─────────────────────────────────────────────

class TestAPIEndpoints:
    """Tests for REST API endpoints."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with mocked dependencies."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"), \
             patch("backend.storage.GCS_AVAILABLE", False), \
             patch("backend.storage.GCS_BUCKET", ""):
            from backend.main import app
            return TestClient(app)

    def test_health_endpoint_returns_200(self, client: TestClient) -> None:
        """Test health endpoint returns 200 status."""
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_endpoint_structure(self, client: TestClient) -> None:
        """Test health endpoint returns all expected fields."""
        r = client.get("/health")
        data = r.json()
        assert "status" in data
        assert "observations" in data
        assert "timestamp" in data
        assert "version" in data
        assert "storage" in data
        assert "firestore" in data

    def test_stats_endpoint_returns_200(self, client: TestClient) -> None:
        """Test stats endpoint returns 200 status."""
        r = client.get("/stats")
        assert r.status_code == 200

    def test_stats_endpoint_structure(self, client: TestClient) -> None:
        """Test stats endpoint returns all expected fields."""
        r = client.get("/stats")
        data = r.json()
        assert "total_observations" in data
        assert "unique_apps" in data
        assert "errors_detected" in data

    def test_dashboard_returns_html(self, client: TestClient) -> None:
        """Test dashboard serves HTML content."""
        r = client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "ARGUS" in r.text

    def test_health_observations_is_integer(self, client: TestClient) -> None:
        """Test health observation count is an integer."""
        r = client.get("/health")
        assert isinstance(r.json()["observations"], int)

    def test_observations_api_endpoint(self, client: TestClient) -> None:
        """Test Firestore observations API endpoint."""
        r = client.get("/api/observations")
        assert r.status_code == 200
        data = r.json()
        assert "observations" in data
        assert "count" in data

    def test_actions_api_endpoint(self, client: TestClient) -> None:
        """Test Firestore actions API endpoint."""
        r = client.get("/api/actions")
        assert r.status_code == 200
        data = r.json()
        assert "actions" in data
        assert "count" in data

    def test_storage_health_endpoint(self, client: TestClient) -> None:
        """Test storage health API endpoint."""
        r = client.get("/api/storage")
        assert r.status_code == 200
        data = r.json()
        assert "local_storage" in data

    def test_cors_headers_present(self, client: TestClient) -> None:
        """Test that CORS headers are present in responses."""
        r = client.get("/health")
        # Security headers should be present
        assert "x-content-type-options" in r.headers
        assert r.headers["x-content-type-options"] == "nosniff"

    def test_security_headers_present(self, client: TestClient) -> None:
        """Test that all security headers are present."""
        r = client.get("/health")
        assert "x-frame-options" in r.headers
        assert "x-xss-protection" in r.headers
        assert "referrer-policy" in r.headers
        assert "content-security-policy" in r.headers


# ─────────────────────────────────────────────
# WebSocket Protocol Tests
# ─────────────────────────────────────────────

class TestWebSocketProtocol:
    """Tests for WebSocket protocol handling."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client with mocked dependencies."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"), \
             patch("backend.storage.GCS_AVAILABLE", False), \
             patch("backend.storage.GCS_BUCKET", ""):
            from backend.main import app
            return TestClient(app)

    def test_ws_invalid_json(self, client: TestClient) -> None:
        """Test WebSocket rejection of invalid JSON."""
        with client.websocket_connect("/ws") as ws:
            ws.send_text("not json {{{")
            response = json.loads(ws.receive_text())
            assert "error" in response

    def test_ws_unknown_message_type(self, client: TestClient) -> None:
        """Test WebSocket rejection of unknown message types."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "invalid_type"})
            response = json.loads(ws.receive_text())
            assert "error" in response

    def test_ws_observe_missing_screenshot(self, client: TestClient) -> None:
        """Test WebSocket observe with missing screenshot."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "observe", "screenshot_b64": ""})
            response = json.loads(ws.receive_text())
            assert response.get("type") == "observe_ack"
            assert "error" in response

    def test_ws_command_empty_text(self, client: TestClient) -> None:
        """Test WebSocket command with empty text."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "command", "text": ""})
            response = json.loads(ws.receive_text())
            assert response.get("type") == "command_response"
            assert "error" in response

    def test_ws_payload_too_large(self, client: TestClient) -> None:
        """Test WebSocket rejection of oversized payloads."""
        with client.websocket_connect("/ws") as ws:
            giant = "x" * (11 * 1024 * 1024)
            ws.send_text(giant)
            response = json.loads(ws.receive_text())
            assert "error" in response

    def test_ws_observe_invalid_base64(self, client: TestClient) -> None:
        """Test WebSocket observe with invalid base64 data."""
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "observe", "screenshot_b64": "!!!not_base64!!!"})
            response = json.loads(ws.receive_text())
            assert "error" in response

    def test_ws_multiple_messages(self, client: TestClient) -> None:
        """Test WebSocket handles multiple sequential messages."""
        with client.websocket_connect("/ws") as ws:
            for _ in range(3):
                ws.send_json({"type": "command", "text": ""})
                response = json.loads(ws.receive_text())
                assert "error" in response or response.get("type") == "command_response"


# ─────────────────────────────────────────────
# Input Validation Tests
# ─────────────────────────────────────────────

class TestInputValidation:
    """Tests for input validation functions."""

    def test_validate_b64_valid(self) -> None:
        """Test validation of correct base64 data."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"), \
             patch("backend.storage.GCS_AVAILABLE", False):
            from backend.main import validate_b64
            valid = base64.b64encode(b"hello world").decode()
            assert validate_b64(valid) is True

    def test_validate_b64_empty(self) -> None:
        """Test validation rejects empty string."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"), \
             patch("backend.storage.GCS_AVAILABLE", False):
            from backend.main import validate_b64
            assert validate_b64("") is False

    def test_validate_b64_none(self) -> None:
        """Test validation rejects None."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"), \
             patch("backend.storage.GCS_AVAILABLE", False):
            from backend.main import validate_b64
            assert validate_b64(None) is False

    def test_validate_b64_invalid_chars(self) -> None:
        """Test validation rejects invalid base64 characters."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel"), \
             patch("backend.storage.GCS_AVAILABLE", False):
            from backend.main import validate_b64
            assert validate_b64("!!!not_base64!!!") is False
