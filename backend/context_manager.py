"""Rolling observation window for ARGUS context management.

Maintains a time-bounded window of screen observations using a deque
with automatic eviction of expired entries. Observations are persisted
to disk as a JSON file for crash recovery.

Typical usage:
    from backend.context_manager import ContextManager

    cm = ContextManager(window_minutes=1)
    cm.add_observation({"app_detected": "VSCode", "activity_summary": "Coding"})
    summary = cm.get_context_summary()
"""

import json
import logging
import os
from collections import deque
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages a rolling time window of screen observations.

    Uses a deque for O(1) append/pop operations and periodically evicts
    observations older than the configured window. Observations are
    persisted to a JSON file on disk for recovery after restarts.

    Attributes:
        window_minutes: Duration of the observation window in minutes.
        observations: Deque of observation dictionaries.
        log_path: Path to the JSON file for disk persistence.
    """

    MAX_OBSERVATIONS: int = 500
    """Maximum number of observations to retain in memory."""

    def __init__(self, window_minutes: int = 5) -> None:
        """Initialize the context manager.

        Creates the log directory if it does not exist and loads any
        previously persisted observations from disk.

        Args:
            window_minutes: Duration of the rolling observation window
                in minutes. Defaults to 5.
        """
        self.window_minutes: int = window_minutes
        self.observations: deque[dict[str, Any]] = deque(maxlen=self.MAX_OBSERVATIONS)
        self.log_path: str = os.path.join("logs", "context.json")
        os.makedirs("logs", exist_ok=True)
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load previously persisted observations from the JSON log file.

        Reads the log file and populates the observations deque, then
        evicts any observations that have expired. Silently handles
        file-not-found and JSON parse errors.
        """
        try:
            if os.path.exists(self.log_path):
                with open(self.log_path, "r", encoding="utf-8") as file_handle:
                    data: dict[str, Any] = json.load(file_handle)
                    for obs in data.get("observations", []):
                        self.observations.append(obs)
                self.clear_old_observations()
                logger.info(
                    "Loaded %d observations from disk", len(self.observations)
                )
        except (json.JSONDecodeError, IOError) as exc:
            logger.warning("Failed to load observations from disk: %s", exc)
            self.observations.clear()

    def _save_to_disk(self) -> None:
        """Persist current observations to the JSON log file.

        Writes the entire observations deque to disk as a JSON array.
        Silently handles write errors to prevent observation loss from
        crashing the application.
        """
        try:
            with open(self.log_path, "w", encoding="utf-8") as file_handle:
                json.dump(
                    {"observations": list(self.observations)},
                    file_handle,
                    indent=2,
                )
        except IOError as exc:
            logger.error("Failed to save observations to disk: %s", exc)

    def add_observation(self, observation: dict[str, Any]) -> None:
        """Add a new observation to the rolling window.

        Automatically timestamps the observation, evicts expired entries,
        and persists the updated state to disk.

        Args:
            observation: Dictionary containing screen analysis data
                (app_detected, activity_summary, etc.).
        """
        observation["timestamp"] = datetime.now().isoformat()
        self.observations.append(observation)
        self.clear_old_observations()
        self._save_to_disk()

    def clear_old_observations(self) -> None:
        """Remove observations older than the configured window.

        Evicts entries from the left side of the deque whose timestamps
        are older than ``window_minutes`` ago.
        """
        cutoff: datetime = datetime.now() - timedelta(minutes=self.window_minutes)
        while self.observations:
            try:
                oldest_ts = datetime.fromisoformat(self.observations[0]["timestamp"])
                if oldest_ts <= cutoff:
                    self.observations.popleft()
                else:
                    break
            except (KeyError, ValueError):
                self.observations.popleft()

    def get_context_window(self) -> list[dict[str, Any]]:
        """Return all observations within the current time window.

        Triggers eviction of expired entries before returning.

        Returns:
            List of observation dictionaries within the active window.
        """
        self.clear_old_observations()
        return list(self.observations)

    def get_context_summary(self) -> str:
        """Generate a human-readable summary of recent observations.

        Formats the rolling observation window into a text summary
        suitable for inclusion in Gemini prompts. Includes timestamps,
        detected apps, activity summaries, errors, URLs, and contextual
        notes.

        Returns:
            Formatted string summarizing recent observations, or a
            message indicating no observations are available.
        """
        observations: list[dict[str, Any]] = self.get_context_window()
        if not observations:
            return "No observations yet. ARGUS just started watching."

        lines: list[str] = [
            f"In the last {self.window_minutes} minutes, ARGUS observed:"
        ]
        for obs in observations:
            try:
                ts: str = datetime.fromisoformat(
                    obs["timestamp"]
                ).strftime("%H:%M:%S")
                app: str = obs.get("app_detected", "unknown app")
                activity: str = obs.get("activity_summary", "")
                error: Any = obs.get("errors_seen")
                url: Any = obs.get("urls_visited")
                files: Any = obs.get("files_open")
                important: Any = obs.get("important_context")

                line: str = f"  [{ts}] {app} — {activity}"
                if error:
                    line += f" | ERROR DETECTED: {error}"
                if url:
                    line += f" | URL: {url}"
                if files:
                    line += f" | File: {files}"
                if important:
                    line += f" | NOTE: {important}"
                lines.append(line)
            except (KeyError, ValueError):
                continue

        return "\n".join(lines)

    def get_observation_count(self) -> int:
        """Return the number of observations in the current window.

        Returns:
            Integer count of active observations.
        """
        return len(self.get_context_window())
