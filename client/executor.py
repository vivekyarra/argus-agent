"""Safe action execution for the ARGUS client agent.

Provides controlled execution of mouse clicks, keyboard typing, and URL
opening with confidence thresholding for safety. Uses PyAutoGUI for
system-level input automation and the ``webbrowser`` module for safe URL
handling (no shell injection).

Typical usage:
    from client.executor import Executor

    executor = Executor()
    executor.click(500, 300, narration="Clicking the submit button")
    executor.type_text("Hello", narration="Typing greeting")
    executor.open_url("https://example.com")
"""

import logging
import time
import webbrowser
from typing import Any, Optional

import pyautogui

logger = logging.getLogger(__name__)

# Allowed URL schemes for open_url to prevent scheme injection
_ALLOWED_SCHEMES: tuple[str, ...] = ("http://", "https://")


class Executor:
    """Safe action executor with confidence thresholding.

    Wraps PyAutoGUI operations with safety controls including failsafe
    mode (move mouse to top-left corner to abort), configurable pause
    between actions, and minimum confidence requirements before executing
    potentially destructive actions.

    Attributes:
        min_confidence: Minimum confidence threshold for action execution.
    """

    def __init__(self, min_confidence: float = 0.6) -> None:
        """Initialize the executor with PyAutoGUI safety controls.

        Enables failsafe mode (emergency stop by moving mouse to
        top-left corner) and sets a default pause between actions.

        Args:
            min_confidence: Minimum confidence score (0.0-1.0) required
                to execute an action. Actions below this threshold are
                logged but not executed. Defaults to 0.6.
        """
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.5
        self.min_confidence: float = min_confidence
        logger.info(
            "Executor initialized (failsafe=True, min_confidence=%.2f)",
            min_confidence,
        )

    def click(self, x: int, y: int, narration: str = "") -> bool:
        """Move the mouse to coordinates and perform a click.

        Args:
            x: Horizontal pixel coordinate to click.
            y: Vertical pixel coordinate to click.
            narration: Optional human-readable description of the action
                for logging purposes.

        Returns:
            True if the click was executed successfully, False on error.
        """
        try:
            if narration:
                logger.info("ARGUS: %s", narration)
            logger.info("Clicking at (%d, %d)", x, y)
            pyautogui.moveTo(x, y, duration=0.5)
            time.sleep(0.2)
            pyautogui.click()
            time.sleep(0.3)
            return True
        except pyautogui.FailSafeException:
            logger.warning("Failsafe triggered — action aborted")
            return False
        except Exception as exc:
            logger.error("Click failed: %s", exc)
            return False

    def type_text(self, text: str, narration: str = "") -> bool:
        """Type text using keyboard simulation.

        Args:
            text: The text string to type.
            narration: Optional human-readable description of the action
                for logging purposes.

        Returns:
            True if the typing was executed successfully, False on error.
        """
        try:
            if narration:
                logger.info("ARGUS: %s", narration)
            logger.info("Typing: %s", text[:50])
            pyautogui.write(text, interval=0.05)
            time.sleep(0.2)
            return True
        except pyautogui.FailSafeException:
            logger.warning("Failsafe triggered — action aborted")
            return False
        except Exception as exc:
            logger.error("Type failed: %s", exc)
            return False

    def open_url(self, url: str, narration: str = "") -> bool:
        """Open a URL in the default browser using the webbrowser module.

        Uses ``webbrowser.open()`` instead of subprocess to prevent
        shell injection vulnerabilities. Only ``http://`` and ``https://``
        schemes are allowed.

        Args:
            url: The URL to open. Must use http or https scheme.
            narration: Optional human-readable description of the action
                for logging purposes.

        Returns:
            True if the URL was opened successfully, False on error or
            if the URL scheme is not allowed.
        """
        try:
            if narration:
                logger.info("ARGUS: %s", narration)

            # Validate URL scheme to prevent injection
            url_stripped: str = url.strip()
            if not any(url_stripped.lower().startswith(s) for s in _ALLOWED_SCHEMES):
                logger.warning("Blocked URL with disallowed scheme: %s", url_stripped[:100])
                return False

            logger.info("Opening URL: %s", url_stripped[:200])
            webbrowser.open(url_stripped)
            time.sleep(1)
            return True
        except Exception as exc:
            logger.error("Open URL failed: %s", exc)
            return False

    def execute_action(self, action_dict: dict[str, Any]) -> bool:
        """Execute an action from a Gemini response dictionary.

        Dispatches to the appropriate handler (click, type, open_url)
        based on the ``action_type`` field. Enforces the minimum
        confidence threshold before executing any action.

        Args:
            action_dict: Dictionary containing the action specification
                with keys: ``narration``, ``action_type``, ``action_target``,
                ``confidence``, ``action_required``, and optionally
                ``coordinates``.

        Returns:
            True if the action was executed successfully (or no action
            was required), False on failure or low confidence.
        """
        try:
            narration: str = str(action_dict.get("narration", ""))
            action_type: str = str(action_dict.get("action_type", "none"))
            action_target: str = str(action_dict.get("action_target", ""))
            confidence: float = float(action_dict.get("confidence", 0.5))
            coordinates: dict[str, Any] = action_dict.get("coordinates", {})

            if action_type == "none" or not action_dict.get("action_required"):
                if narration:
                    logger.info("ARGUS: %s", narration)
                return True

            if confidence < self.min_confidence:
                logger.info("ARGUS: %s", narration)
                logger.warning(
                    "Low confidence (%.2f < %.2f). Skipping action for safety.",
                    confidence,
                    self.min_confidence,
                )
                return False

            if action_type == "click":
                coords: dict[str, Any] = coordinates
                if (
                    coords
                    and coords.get("found")
                    and coords.get("x") is not None
                    and coords.get("y") is not None
                ):
                    return self.click(int(coords["x"]), int(coords["y"]), narration)
                else:
                    logger.warning("Could not find element: %s", action_target)
                    if narration:
                        logger.info("ARGUS: %s", narration)
                    return False

            elif action_type == "type":
                return self.type_text(action_target, narration)

            elif action_type == "open_url":
                return self.open_url(action_target, narration)

            logger.warning("Unknown action type: %s", action_type)
            return True
        except Exception as exc:
            logger.error("execute_action error: %s", exc)
            return False
