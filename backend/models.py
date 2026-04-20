"""Pydantic V2 validation models for ARGUS WebSocket messages.

Provides strict input validation for all WebSocket payloads using
Pydantic V2 ``strict`` mode. Every field is typed, constrained, and
documented to prevent injection, overflow, and malformed data attacks.

Mitigates: OWASP A03:2021 — Injection by ensuring all user input
is validated before processing.

Typical usage:
    from backend.models import ObserveMessage, CommandMessage, parse_ws_message

    data = parse_ws_message(raw_json)
    if isinstance(data, ObserveMessage):
        process_observation(data)
"""

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class ObserveMessage(BaseModel, strict=True):
    """Validated WebSocket observation message.

    Attributes:
        type: Must be exactly ``observe``.
        screenshot_b64: Base64-encoded PNG screenshot data.
    """

    type: Literal["observe"]
    screenshot_b64: str = Field(
        ...,
        min_length=100,
        max_length=10_485_760,
        description="Base64-encoded PNG screenshot (max 10MB)",
    )

    @field_validator("screenshot_b64")
    @classmethod
    def validate_b64_chars(cls, v: str) -> str:
        """Validate that the string contains only valid base64 characters.

        Mitigates: OWASP A03:2021 — Injection via malformed base64.

        Args:
            v: The base64 string to validate.

        Returns:
            The validated base64 string.

        Raises:
            ValueError: If invalid characters are found.
        """
        import re

        if not re.match(r"^[A-Za-z0-9+/=\s]+$", v):
            raise ValueError("Invalid base64 characters detected")
        return v


class CommandMessage(BaseModel, strict=True):
    """Validated WebSocket command message.

    Attributes:
        type: Must be exactly ``command``.
        text: The user's command text.
        screenshot_b64: Optional base64-encoded screenshot for context.
    """

    type: Literal["command"]
    text: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="User command text (max 1000 chars)",
    )
    screenshot_b64: Optional[str] = Field(
        default=None,
        max_length=10_485_760,
        description="Optional base64-encoded screenshot",
    )

    @field_validator("text")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        """Sanitize command text by removing dangerous characters.

        Mitigates: OWASP A03:2021 — Injection via control characters.

        Args:
            v: Raw command text.

        Returns:
            Sanitized command text.

        Raises:
            ValueError: If text is empty after sanitization.
        """
        import re

        # Remove null bytes
        v = v.replace("\x00", "")
        # Remove ANSI escape sequences
        v = re.sub(r"\x1b\[[0-9;]*m", "", v)
        # Remove control characters (keep newlines and tabs)
        v = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", v)
        v = v.strip()
        if not v:
            raise ValueError("Command text is empty after sanitization")
        return v


class WebSocketError(BaseModel):
    """Error response model for WebSocket communication.

    Attributes:
        error: Human-readable error description.
        retry_after_seconds: Optional retry delay for rate limiting.
    """

    error: str
    retry_after_seconds: Optional[int] = None


class ObserveAck(BaseModel):
    """Acknowledgment response for observation messages.

    Attributes:
        type: Always ``observe_ack``.
        observation: Extracted observation data.
        total_observations: Current observation count.
        error: Optional error message.
    """

    type: Literal["observe_ack"] = "observe_ack"
    observation: Optional[dict[str, Any]] = None
    total_observations: Optional[int] = None
    error: Optional[str] = None


class CommandResponse(BaseModel):
    """Response model for command messages.

    Attributes:
        type: Always ``command_response``.
        narration: AI-generated spoken response.
        action_required: Whether an action should be executed.
        action_type: Type of action (click, type, open_url, none).
        action_target: Target for the action.
        confidence: Confidence score for the action.
        coordinates: Element coordinates for click actions.
        error: Optional error message.
    """

    type: Literal["command_response"] = "command_response"
    narration: str = ""
    action_required: bool = False
    action_type: str = "none"
    action_target: str = ""
    confidence: float = 0.5
    coordinates: Optional[dict[str, Any]] = None
    error: Optional[str] = None


def parse_ws_message(raw_json: str) -> Union[ObserveMessage, CommandMessage, None]:
    """Parse and validate a raw WebSocket JSON message.

    Determines the message type from the ``type`` field and validates
    the full payload against the appropriate Pydantic model.

    Mitigates: OWASP A03:2021 — Injection by rejecting any payload
    that does not conform to the expected schema.

    Args:
        raw_json: Raw JSON string from the WebSocket.

    Returns:
        Validated ObserveMessage or CommandMessage, or None if
        validation fails.

    Raises:
        ValueError: If the JSON is malformed or the message type
            is unrecognized.
    """
    import json

    try:
        data: dict[str, Any] = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    msg_type: str = data.get("type", "")

    if msg_type == "observe":
        return ObserveMessage(**data)
    elif msg_type == "command":
        return CommandMessage(**data)
    else:
        raise ValueError(f"Unknown message type: {msg_type}")
