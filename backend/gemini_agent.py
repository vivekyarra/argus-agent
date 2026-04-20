"""Gemini 2.0 Flash Vision integration for ARGUS screen analysis.

Provides the AI-powered analysis engine that processes screenshots,
responds to user commands with contextual awareness, and locates UI
elements for autonomous action execution. All interactions use structured
JSON prompts with safe defaults on parse failure.

Typical usage:
    from backend.gemini_agent import GeminiAgent

    agent = GeminiAgent()
    observation = agent.analyze_screenshot(pil_image)
    response = agent.respond_to_user("help me debug", context_summary)
    coords = agent.find_element_coordinates(pil_image, "Submit button")
"""

import json
import logging
import os
import re
import base64
import time
from io import BytesIO
from typing import Any, Optional

import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class GeminiAgent:
    """AI agent powered by Gemini 2.0 Flash for multimodal screen analysis.

    Handles three core operations:
    1. Screenshot analysis — extracting structured context from screen frames.
    2. User command response — context-aware conversational responses.
    3. UI element detection — pixel-coordinate localization for action execution.

    All API calls include retry logic with exponential backoff and return
    safe defaults on failure to ensure zero crashes from malformed AI output.

    Attributes:
        model: The configured Gemini GenerativeModel instance.
        max_retries: Maximum number of retry attempts for API calls.
        retry_delay: Base delay in seconds between retries.
    """

    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """Initialize the Gemini agent with API credentials.

        Configures the Gemini API client using the ``GEMINI_API_KEY``
        environment variable and creates a GenerativeModel instance
        for the ``gemini-2.0-flash-lite`` model.

        Args:
            max_retries: Maximum retry attempts for failed API calls.
                Defaults to 3.
            retry_delay: Base delay in seconds between retries, with
                exponential backoff. Defaults to 1.0.

        Raises:
            ValueError: If ``GEMINI_API_KEY`` is not set in environment.
        """
        api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in .env file")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.0-flash-lite")
        self.max_retries: int = max_retries
        self.retry_delay: float = retry_delay
        logger.info("GeminiAgent initialized with gemini-2.0-flash-lite")

    def _parse_json_response(self, text: str) -> dict[str, Any]:
        """Parse a JSON response from Gemini, stripping markdown fences.

        Handles common LLM output patterns including markdown code blocks
        (````` ```json ... ``` `````) and leading/trailing whitespace.

        Args:
            text: Raw text response from the Gemini API.

        Returns:
            Parsed dictionary from the JSON response, or an empty dict
            if parsing fails.
        """
        try:
            text = text.strip()
            text = re.sub(r"^```json\s*", "", text)
            text = re.sub(r"^```\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()
            return json.loads(text)
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("JSON parse failed: %s | Raw: %s", exc, text[:200])
            return {}

    def _image_to_part(self, pil_image: Image.Image) -> dict[str, str]:
        """Convert a PIL Image to a Gemini API inline data part.

        Encodes the image as PNG and base64-encodes it for transmission
        to the Gemini multimodal API.

        Args:
            pil_image: The PIL Image to convert.

        Returns:
            Dictionary with ``mime_type`` and ``data`` keys suitable
            for Gemini API content parts.
        """
        buf = BytesIO()
        pil_image.save(buf, format="PNG", optimize=True)
        b64: str = base64.b64encode(buf.getvalue()).decode()
        return {"mime_type": "image/png", "data": b64}

    def _call_with_retry(self, content: Any) -> Optional[str]:
        """Call the Gemini API with exponential backoff retry logic.

        Args:
            content: The content to send to ``generate_content`` (can be
                a string, list of parts, etc.).

        Returns:
            The text response from Gemini, or None if all retries fail.
        """
        for attempt in range(self.max_retries):
            try:
                response = self.model.generate_content(content)
                return response.text
            except Exception as exc:
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(
                    "Gemini API call failed (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1, self.max_retries, exc, wait_time,
                )
                if attempt < self.max_retries - 1:
                    time.sleep(wait_time)
        return None

    def analyze_screenshot(self, pil_image: Image.Image) -> dict[str, Any]:
        """Analyze a screenshot and extract structured context information.

        Sends the image to Gemini 2.0 Flash Vision with a structured
        prompt requesting app detection, activity summary, error detection,
        URL extraction, and contextual notes.

        Args:
            pil_image: The screenshot to analyze as a PIL Image.

        Returns:
            Dictionary containing analysis results with guaranteed keys:
            ``app_detected``, ``activity_summary``, ``errors_seen``,
            ``urls_visited``, ``files_open``, ``important_context``.
            Returns safe defaults if the API call or parsing fails.
        """
        default: dict[str, Any] = {
            "app_detected": "unknown",
            "activity_summary": "Screen captured",
            "errors_seen": None,
            "urls_visited": None,
            "files_open": None,
            "important_context": None,
        }
        try:
            prompt: str = (
                "You are ARGUS, an ambient screen monitoring agent. "
                "Analyze this screenshot and extract structured information.\n"
                "Return ONLY a valid JSON object with these exact keys:\n"
                "{\n"
                '  "app_detected": "name of the main application visible",\n'
                '  "activity_summary": "one sentence describing what the user is doing",\n'
                '  "errors_seen": "any error messages visible, or null",\n'
                '  "urls_visited": "any URLs visible in browser address bar, or null",\n'
                '  "files_open": "any file names visible in tabs or title bar, or null",\n'
                '  "important_context": "anything that looks like a problem the user is struggling with, or null"\n'
                "}\n"
                "Return ONLY the JSON. No markdown. No explanation. No extra text."
            )
            response_text = self._call_with_retry([prompt, self._image_to_part(pil_image)])
            if not response_text:
                return default
            result = self._parse_json_response(response_text)
            if not result:
                return default
            return {**default, **result}
        except Exception as exc:
            logger.error("analyze_screenshot error: %s", exc)
            return default

    def respond_to_user(self, user_command: str, context_summary: str) -> dict[str, Any]:
        """Generate a context-aware response to a user command.

        Uses the rolling observation window summary to craft a response
        that references what ARGUS actually observed on screen, rather
        than requiring the user to explain their situation.

        Args:
            user_command: The user's voice or text command.
            context_summary: Summary of recent screen observations from
                the ContextManager.

        Returns:
            Dictionary containing the response with guaranteed keys:
            ``narration``, ``action_required``, ``action_type``,
            ``action_target``, ``confidence``.
        """
        default: dict[str, Any] = {
            "narration": "I see what you need. Let me help.",
            "action_required": False,
            "action_type": "none",
            "action_target": "",
            "confidence": 0.5,
        }
        try:
            prompt: str = (
                "You are ARGUS, an AI agent with 100 eyes that has been silently "
                "watching the user's screen for the last 1 minute. You have deep "
                "context about what they have been doing. You are calm, precise, "
                "and helpful like a brilliant colleague sitting next to them.\n\n"
                "Here is everything you observed in the last 1 minute:\n"
                f"{context_summary}\n\n"
                f'The user just said: "{user_command}"\n\n'
                "Based on what you OBSERVED (not what they told you), respond helpfully. "
                "If you can see a specific fix, give it. If you saw them struggle with "
                "something, address it directly. Be specific — reference actual things "
                "you saw.\n\n"
                "Return ONLY a valid JSON object:\n"
                "{\n"
                '  "narration": "your spoken response to the user, 2-3 sentences max, '
                'conversational and specific to what you observed",\n'
                '  "action_required": true or false,\n'
                '  "action_type": "click" or "type" or "open_url" or "none",\n'
                '  "action_target": "if click: describe the UI element to click. '
                'if type: the exact text to type. if open_url: the URL. otherwise empty string",\n'
                '  "confidence": 0.0 to 1.0\n'
                "}\n"
                "Return ONLY the JSON. No markdown. No explanation."
            )
            response_text = self._call_with_retry(prompt)
            if not response_text:
                return default
            result = self._parse_json_response(response_text)
            if not result:
                return default
            return {**default, **result}
        except Exception as exc:
            logger.error("respond_to_user error: %s", exc)
            return default

    def find_element_coordinates(
        self, pil_image: Image.Image, element_description: str
    ) -> dict[str, Any]:
        """Locate a UI element's pixel coordinates in a screenshot.

        Uses Gemini's vision capabilities to find the described UI element
        and return its center coordinates for click automation.

        Args:
            pil_image: The screenshot containing the target element.
            element_description: Natural language description of the UI
                element to find (e.g., "Submit button", "search bar").

        Returns:
            Dictionary with keys ``found`` (bool), ``x`` (int or None),
            ``y`` (int or None), ``confidence`` (float), and
            ``description`` (str).
        """
        default: dict[str, Any] = {
            "found": False,
            "x": None,
            "y": None,
            "confidence": 0.0,
            "description": "Element not found",
        }
        try:
            prompt: str = (
                "Look at this screenshot carefully. Find the UI element described "
                f'as: "{element_description}"\n\n'
                f"The image is {pil_image.width} pixels wide and "
                f"{pil_image.height} pixels tall.\n\n"
                "Return ONLY a valid JSON object:\n"
                "{\n"
                '  "found": true or false,\n'
                '  "x": pixel x coordinate of the center of the element (integer),\n'
                '  "y": pixel y coordinate of the center of the element (integer),\n'
                '  "confidence": 0.0 to 1.0,\n'
                '  "description": "what you found at those coordinates"\n'
                "}\n"
                "Return ONLY JSON. No markdown. No explanation. "
                "If you cannot find the element, set found to false and x and y to null."
            )
            response_text = self._call_with_retry([prompt, self._image_to_part(pil_image)])
            if not response_text:
                return default
            result = self._parse_json_response(response_text)
            if not result:
                return default
            return {**default, **result}
        except Exception as exc:
            logger.error("find_element_coordinates error: %s", exc)
            return default
