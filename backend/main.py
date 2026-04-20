"""ARGUS Backend — FastAPI application with WebSocket and REST endpoints.

Provides the server-side API for the ARGUS ambient AI screen intelligence
agent. Includes real-time WebSocket communication for screen observation
and command processing, REST endpoints for health monitoring and statistics,
Firestore-backed data persistence, and security middleware.

Endpoints:
    GET  /                  Interactive HTML dashboard
    GET  /health            System health and version information
    GET  /stats             Live observation statistics
    GET  /api/observations  Recent observations from Firestore
    GET  /api/actions       Recent action logs from Firestore
    GET  /api/storage       Storage backend health status
    WS   /ws                Real-time screen observation and command stream

Security:
    - CORS middleware with configurable origins
    - Security headers (CSP, X-Frame-Options, etc.)
    - Rate limiting per client IP
    - WebSocket API key authentication
    - Input validation and sanitization
"""

import base64
import json
import logging
import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# ── Cloud Logging Integration ────────────────────────────────────────
# When deployed on GCP, Cloud Logging auto-captures structured logs.
# This integrates Python's logging module with Cloud Logging for
# production observability, alerting, and audit trail compliance.
try:
    import google.cloud.logging as cloud_logging

    cloud_client = cloud_logging.Client()
    cloud_client.setup_logging()
    _CLOUD_LOGGING_AVAILABLE: bool = True
except (ImportError, Exception):
    _CLOUD_LOGGING_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.context_manager import ContextManager
from backend.storage import Storage
from backend.gemini_agent import GeminiAgent
from backend.firestore_client import FirestoreClient
from backend.secret_manager import get_secret, health_check as sm_health_check
from backend.models import parse_ws_message, ObserveMessage, CommandMessage
from backend.security import (
    RateLimiter,
    SecurityHeadersMiddleware,
    authenticate_websocket,
    sanitize_command,
    validate_api_key,
)

# ── Application Setup ────────────────────────────────────────────────

app = FastAPI(
    title="ARGUS Backend",
    description=(
        "Ambient AI Screen Intelligence Agent powered by Gemini 2.0 Flash Vision. "
        "Provides real-time screen observation, context-aware command processing, "
        "and autonomous action execution."
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── Middleware ────────────────────────────────────────────────────────

# CORS
cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# ── Service Initialization ───────────────────────────────────────────

context_manager = ContextManager(
    window_minutes=int(os.getenv("CONTEXT_WINDOW_MINUTES", "1"))
)
storage = Storage()
gemini_agent = GeminiAgent()
firestore_db = FirestoreClient()
rate_limiter = RateLimiter(
    max_requests=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
    window_seconds=60,
)

# ── Constants ────────────────────────────────────────────────────────

MAX_B64_SIZE: int = 10 * 1024 * 1024  # 10 MB limit
MAX_COMMAND_LENGTH: int = 1000


# ── Utility Functions ────────────────────────────────────────────────


def validate_b64(b64_string: Optional[str]) -> bool:
    """Validate a base64-encoded string for correctness and size constraints.

    Checks that the string is non-empty, within the maximum size limit,
    and contains valid base64 encoding.

    Args:
        b64_string: The base64 string to validate.

    Returns:
        True if the string is valid base64 within size limits, False otherwise.
    """
    if not b64_string or len(b64_string) > MAX_B64_SIZE:
        return False
    try:
        base64.b64decode(b64_string, validate=True)
        return True
    except Exception:
        return False


def b64_to_image(b64_string: str) -> Image.Image:
    """Decode a base64 PNG string to a PIL Image.

    Args:
        b64_string: Base64-encoded PNG image data.

    Returns:
        PIL Image instance in RGB mode.

    Raises:
        ValueError: If the base64 data cannot be decoded to a valid image.
    """
    img_data: bytes = base64.b64decode(b64_string)
    return Image.open(BytesIO(img_data)).convert("RGB")


def _get_client_ip(websocket: WebSocket) -> str:
    """Extract the client IP address from a WebSocket connection.

    Args:
        websocket: The WebSocket connection object.

    Returns:
        Client IP address string, or ``unknown`` if not available.
    """
    if websocket.client:
        return websocket.client.host
    return "unknown"


# ── REST Endpoints ───────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    """Serve the interactive ARGUS dashboard.

    Returns:
        HTML response containing the live dashboard page.
    """
    html_path: Path = Path(__file__).parent / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>ARGUS is watching.</h1>")


@app.get("/health")
async def health() -> JSONResponse:
    """Return system health information.

    Provides version, model, observation count, storage backend status,
    Firestore connectivity, and the current server timestamp.

    Returns:
        JSON response with health status fields.
    """
    return JSONResponse({
        "status": "operational",
        "version": "2.2.0",
        "observations": context_manager.get_observation_count(),
        "timestamp": datetime.now().isoformat(),
        "model": "gemini-2.0-flash-lite",
        "storage": storage.health_check(),
        "firestore": firestore_db.health_check(),
        "secret_manager": sm_health_check(),
        "cloud_logging": _CLOUD_LOGGING_AVAILABLE,
    })


@app.get("/stats")
async def stats() -> JSONResponse:
    """Return live observation statistics.

    Aggregates information about detected applications, errors, and
    the current context window configuration.

    Returns:
        JSON response with statistical data.
    """
    obs: list[dict[str, Any]] = context_manager.get_context_window()
    apps_seen: list[str] = list({
        o.get("app_detected", "unknown") for o in obs if o.get("app_detected")
    })
    errors: list[Any] = [o.get("errors_seen") for o in obs if o.get("errors_seen")]
    return JSONResponse({
        "total_observations": len(obs),
        "unique_apps": apps_seen,
        "errors_detected": len(errors),
        "context_window_minutes": context_manager.window_minutes,
        "timestamp": datetime.now().isoformat(),
    })


@app.get("/api/observations")
async def get_observations() -> JSONResponse:
    """Retrieve recent observations from Firestore.

    Returns the most recent 50 screen observations stored in
    Cloud Firestore, ordered by storage time descending.

    Returns:
        JSON response with list of observation records.
    """
    observations: list[dict[str, Any]] = firestore_db.get_recent_observations(limit=50)
    return JSONResponse({
        "observations": observations,
        "count": len(observations),
        "source": "firestore" if firestore_db.available else "unavailable",
    })


@app.get("/api/actions")
async def get_actions() -> JSONResponse:
    """Retrieve recent action logs from Firestore.

    Returns the most recent 50 action log entries stored in
    Cloud Firestore, ordered by storage time descending.

    Returns:
        JSON response with list of action log records.
    """
    actions: list[dict[str, Any]] = firestore_db.get_recent_actions(limit=50)
    return JSONResponse({
        "actions": actions,
        "count": len(actions),
        "source": "firestore" if firestore_db.available else "unavailable",
    })


@app.get("/api/storage")
async def storage_health() -> JSONResponse:
    """Return storage backend health status.

    Reports the status of both local filesystem storage and Google
    Cloud Storage connectivity.

    Returns:
        JSON response with storage health information.
    """
    return JSONResponse(storage.health_check())


# ── WebSocket Endpoint ───────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Handle real-time WebSocket communication with ARGUS clients.

    Supports two message types:
    - ``observe``: Process a screenshot for ambient context building.
    - ``command``: Process a user command with context-aware AI response.

    Connections are authenticated via API key (if configured) and
    rate-limited per client IP address.

    Args:
        websocket: The incoming WebSocket connection.
    """
    # Authenticate
    if not await authenticate_websocket(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    client_ip: str = _get_client_ip(websocket)
    logger.info("Client connected: %s", client_ip)

    # Track session in Firestore
    firestore_db.store_session({
        "client_ip": client_ip,
        "connected_at": datetime.now().isoformat(),
        "status": "active",
    })

    try:
        while True:
            raw: str = await websocket.receive_text()

            # Rate limiting
            if not rate_limiter.is_allowed(client_ip):
                await websocket.send_text(json.dumps({
                    "error": "Rate limit exceeded. Try again later.",
                    "retry_after_seconds": 60,
                }))
                continue

            # Payload size check
            if len(raw) > MAX_B64_SIZE + 1024:
                await websocket.send_text(json.dumps({"error": "Payload too large"}))
                continue

            # Parse JSON
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            msg_type: Optional[str] = data.get("type")

            if msg_type == "observe":
                await _handle_observe(websocket, data)

            elif msg_type == "command":
                await _handle_command(websocket, data)

            else:
                await websocket.send_text(json.dumps({
                    "error": f"Unknown message type: {msg_type}"
                }))

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", client_ip)
    except Exception as exc:
        logger.error("Unexpected WebSocket error for %s: %s", client_ip, exc)


async def _handle_observe(websocket: WebSocket, data: dict[str, Any]) -> None:
    """Process an observation message from the WebSocket client.

    Validates and decodes the screenshot, runs Gemini analysis, stores
    the observation in context manager and Firestore, and saves the
    screenshot to storage.

    Args:
        websocket: The active WebSocket connection.
        data: Parsed JSON message with ``screenshot_b64`` field.
    """
    try:
        b64: str = data.get("screenshot_b64", "")
        if not validate_b64(b64):
            await websocket.send_text(json.dumps({
                "type": "observe_ack",
                "error": "Invalid or missing screenshot",
            }))
            return

        pil_image: Image.Image = b64_to_image(b64)
        if pil_image.width > 4096 or pil_image.height > 4096:
            await websocket.send_text(json.dumps({
                "type": "observe_ack",
                "error": "Image dimensions too large (max 4096x4096)",
            }))
            return

        observation: dict[str, Any] = gemini_agent.analyze_screenshot(pil_image)
        observation["timestamp"] = datetime.now().isoformat()
        context_manager.add_observation(observation)

        ts: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage.save_screenshot(pil_image, ts)
        context_manager.clear_old_observations()

        # Persist to Firestore
        firestore_db.store_observation(observation)

        await websocket.send_text(json.dumps({
            "type": "observe_ack",
            "observation": observation,
            "total_observations": context_manager.get_observation_count(),
        }))
    except Exception as exc:
        logger.error("Observe handler error: %s", exc)
        await websocket.send_text(json.dumps({
            "type": "observe_ack",
            "error": str(exc),
        }))


async def _handle_command(websocket: WebSocket, data: dict[str, Any]) -> None:
    """Process a command message from the WebSocket client.

    Sanitizes the command, generates a context-aware response using
    Gemini, optionally resolves click coordinates, and logs the action
    to both local storage and Firestore.

    Args:
        websocket: The active WebSocket connection.
        data: Parsed JSON message with ``text`` and optional
            ``screenshot_b64`` fields.
    """
    try:
        command_text: str = sanitize_command(
            str(data.get("text", "")), MAX_COMMAND_LENGTH
        )
        if not command_text.strip():
            await websocket.send_text(json.dumps({
                "type": "command_response",
                "error": "Empty command",
            }))
            return

        b64: str = data.get("screenshot_b64", "")
        context_summary: str = context_manager.get_context_summary()
        response: dict[str, Any] = gemini_agent.respond_to_user(
            command_text, context_summary
        )

        if (
            response.get("action_required")
            and response.get("action_type") == "click"
            and b64
            and validate_b64(b64)
        ):
            pil_image: Image.Image = b64_to_image(b64)
            target: str = response.get("action_target", "")
            coords: dict[str, Any] = gemini_agent.find_element_coordinates(
                pil_image, target
            )
            response["coordinates"] = coords
        else:
            response["coordinates"] = {"found": False, "x": None, "y": None}

        # Log action
        action_log: dict[str, Any] = {
            "command": command_text,
            "response": response,
            "context_length": context_manager.get_observation_count(),
        }
        storage.save_action_log(action_log)
        firestore_db.store_action(action_log)

        response["type"] = "command_response"
        await websocket.send_text(json.dumps(response))
    except Exception as exc:
        logger.error("Command handler error: %s", exc)
        await websocket.send_text(json.dumps({
            "type": "command_response",
            "narration": "I encountered an error processing your command.",
            "action_required": False,
            "error": str(exc),
        }))


# ── Application Entry Point ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
