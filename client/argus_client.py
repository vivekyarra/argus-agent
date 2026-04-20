"""ARGUS Client — Main orchestrator for ambient screen observation.

Connects to the ARGUS backend via WebSocket and runs two concurrent
loops: an observation loop that captures and sends screenshots at
configurable intervals, and a command loop that listens for voice/text
commands and executes AI-generated actions.

The client features:
- Automatic reconnection with exponential backoff
- Intelligent pixel-diff filtering to reduce API calls
- Voice activation with configurable wake word
- Keyboard fallback when no microphone is available
- Safe action execution with confidence thresholding

Typical usage:
    python -m client.argus_client
"""

import asyncio
import json
import logging
import os
import sys
import time
from typing import Any, Optional

import websockets
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from client.screen_capture import ScreenCapture
from client.voice_listener import VoiceListener
from client.executor import Executor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────

BACKEND_URL: str = os.getenv("BACKEND_URL", "ws://localhost:8000/ws")
SCREENSHOT_INTERVAL: int = int(os.getenv("SCREENSHOT_INTERVAL", "10"))
PIXEL_DIFF_THRESHOLD: float = float(os.getenv("PIXEL_DIFF_THRESHOLD", "15"))

BANNER: str = """
╔═══════════════════════════════════════════════╗
║              A  R  G  U  S                    ║
║        "It never stops watching."             ║
║                                               ║
║   👁️  Observing your screen every 10 sec     ║
║   🎤  Say "ARGUS" to activate                 ║
║   ⌨️  No mic? Just type when prompted         ║
║   🖱️  Move mouse to top-left to STOP          ║
╚═══════════════════════════════════════════════╝
"""


# ── Observation Loop ─────────────────────────────────────────────────


async def observation_loop(
    websocket: Any,
    screen_capture: ScreenCapture,
    stop_event: asyncio.Event,
) -> None:
    """Continuously capture and send screenshots to the backend.

    Captures screenshots at the configured interval, applies pixel-diff
    filtering to skip unchanged frames, and sends significant changes
    to the backend via WebSocket.

    Args:
        websocket: Active WebSocket connection to the backend.
        screen_capture: ScreenCapture instance for frame acquisition.
        stop_event: Event to signal graceful shutdown of the loop.
    """
    last_send_time: float = 0
    dot_count: int = 0
    while not stop_event.is_set():
        try:
            now: float = time.time()
            b64: str = screen_capture.capture_b64()
            should_send: bool = (
                screen_capture.has_significant_change(b64, PIXEL_DIFF_THRESHOLD)
                or (now - last_send_time) >= SCREENSHOT_INTERVAL
            )
            if should_send:
                await websocket.send(json.dumps({
                    "type": "observe",
                    "screenshot_b64": b64,
                }))
                last_send_time = now
                dot_count += 1
                dots: str = "." * (dot_count % 4 + 1)
                print(f"\r[ARGUS watching{dots}]   ", end="", flush=True)

            await asyncio.sleep(2)
        except Exception as exc:
            logger.error("Observation loop error: %s", exc)
            await asyncio.sleep(5)


# ── Response Receiver ────────────────────────────────────────────────


async def response_receiver(
    websocket: Any,
    stop_event: asyncio.Event,
) -> Optional[dict[str, Any]]:
    """Receive and parse a single response from the backend.

    Waits for a WebSocket message with a 1-second timeout per iteration.
    Observation acknowledgments are silently consumed; command responses
    are returned for processing.

    Args:
        websocket: Active WebSocket connection to the backend.
        stop_event: Event to signal graceful shutdown.

    Returns:
        Parsed response dictionary, or None if the loop is stopped
        or no response is received.
    """
    while not stop_event.is_set():
        try:
            raw: str = await asyncio.wait_for(websocket.recv(), timeout=1.0)
            data: dict[str, Any] = json.loads(raw)
            if data.get("type") == "observe_ack":
                obs: dict[str, Any] = data.get("observation", {})
                app: str = obs.get("app_detected", "")
                if app:
                    pass  # Silent observation tracking
            return data
        except asyncio.TimeoutError:
            continue
        except Exception as exc:
            logger.error("Response receiver error: %s", exc)
            await asyncio.sleep(1)
    return None


# ── Command Loop ─────────────────────────────────────────────────────


async def command_loop(
    websocket: Any,
    screen_capture: ScreenCapture,
    voice_listener: VoiceListener,
    executor: Executor,
    stop_event: asyncio.Event,
) -> None:
    """Listen for user commands and process them through the backend.

    Waits for wake word activation (voice or keyboard), captures a fresh
    screenshot, sends the command to the backend, and executes any
    resulting actions.

    Args:
        websocket: Active WebSocket connection to the backend.
        screen_capture: ScreenCapture instance for frame acquisition.
        voice_listener: VoiceListener instance for speech recognition.
        executor: Executor instance for action execution.
        stop_event: Event to signal graceful shutdown of the loop.
    """
    while not stop_event.is_set():
        try:
            wake: Optional[str] = await asyncio.get_event_loop().run_in_executor(
                None, voice_listener.listen_for_wake_word
            )

            if wake is None and not voice_listener.microphone_available:
                user_input: str = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: input(
                        "\nPress Enter + type command (or type 'argus <command>'): "
                    ),
                )
                if not user_input.lower().startswith("argus"):
                    continue
                wake = user_input

            if wake:
                try:
                    import winsound

                    winsound.Beep(1000, 200)
                except ImportError:
                    pass

                print("\n" + "=" * 50)
                print("👁️  ARGUS ACTIVATED — Listening for command...")
                print("=" * 50)

                if voice_listener.microphone_available:
                    command: str = await asyncio.get_event_loop().run_in_executor(
                        None, voice_listener.listen_for_command
                    )
                else:
                    raw_input: str = wake
                    if raw_input.lower().startswith("argus"):
                        command = raw_input[5:].strip()
                    else:
                        command = raw_input

                if not command:
                    logger.info("No command received")
                    continue

                logger.info("Processing command: '%s'", command)
                b64: str = screen_capture.capture_b64()

                await websocket.send(json.dumps({
                    "type": "command",
                    "text": command,
                    "screenshot_b64": b64,
                }))

                try:
                    raw: str = await asyncio.wait_for(
                        websocket.recv(), timeout=30.0
                    )
                    response: dict[str, Any] = json.loads(raw)
                    narration: str = response.get(
                        "narration", "I see what you need."
                    )
                    print(f"\n🤖 ARGUS: {narration}\n")
                    executor.execute_action(response)
                except asyncio.TimeoutError:
                    logger.warning("Response timed out. Gemini may be slow.")
                except Exception as exc:
                    logger.error("Command response error: %s", exc)

            await asyncio.sleep(0.5)

        except Exception as exc:
            logger.error("Command loop error: %s", exc)
            await asyncio.sleep(2)


# ── Main Entry Point ────────────────────────────────────────────────


async def main() -> None:
    """Run the ARGUS client with automatic reconnection.

    Initializes all client subsystems and connects to the backend
    via WebSocket. On disconnection, retries with exponential backoff
    up to a maximum delay of 60 seconds.
    """
    print(BANNER)

    screen_capture = ScreenCapture()
    voice_listener = VoiceListener()
    executor = Executor()
    stop_event = asyncio.Event()

    retry_delay: int = 5
    while True:
        try:
            logger.info("Connecting to backend at %s...", BACKEND_URL)
            async with websockets.connect(
                BACKEND_URL, ping_interval=20, ping_timeout=60
            ) as websocket:
                logger.info("Connected. Starting observation...")
                retry_delay = 5

                obs_task: asyncio.Task = asyncio.create_task(
                    observation_loop(websocket, screen_capture, stop_event)
                )
                cmd_task: asyncio.Task = asyncio.create_task(
                    command_loop(
                        websocket,
                        screen_capture,
                        voice_listener,
                        executor,
                        stop_event,
                    )
                )

                await asyncio.gather(obs_task, cmd_task)

        except OSError:
            logger.warning(
                "Backend not running. Retrying in %ds...", retry_delay
            )
            logger.info(
                "Make sure backend is running: uvicorn backend.main:app --port 8000"
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)
        except Exception as exc:
            logger.error(
                "Connection error: %s. Retrying in %ds...", exc, retry_delay
            )
            await asyncio.sleep(retry_delay)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down. Goodbye.")
