"""Google Cloud Storage and local filesystem persistence for ARGUS.

Provides dual-write storage that persists screenshots and action logs
to both local filesystem and Google Cloud Storage. Gracefully falls back
to local-only storage when GCS is unavailable or unconfigured.

Typical usage:
    from backend.storage import Storage

    storage = Storage()
    path = storage.save_screenshot(pil_image, timestamp="20260420_120000")
    storage.save_action_log({"command": "help", "response": {...}})
    recent = storage.get_recent_screenshots(n=5)
"""

import json
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any, Optional

from PIL import Image

logger = logging.getLogger(__name__)

try:
    from google.cloud import storage as gcs

    GCS_AVAILABLE: bool = True
except ImportError:
    GCS_AVAILABLE = False
    logger.info("google-cloud-storage not installed; GCS disabled")

GCS_BUCKET: str = os.getenv("GCS_BUCKET_NAME", "argus-agent-storage")


class Storage:
    """Dual-write storage backend with GCS and local filesystem support.

    Persists screenshots as PNG files and action logs as JSONL entries
    to both the local filesystem and Google Cloud Storage. GCS uploads
    are best-effort and do not block local storage operations.

    Attributes:
        logs_dir: Local directory for log files.
        screenshots_dir: Local directory for screenshot PNG files.
        actions_log: Path to the local JSONL action log file.
        gcs_client: Google Cloud Storage client, or None if unavailable.
        bucket: GCS bucket instance, or None if unavailable.
    """

    def __init__(self) -> None:
        """Initialize the storage backend.

        Creates local directories and attempts to connect to Google
        Cloud Storage using the bucket name from the ``GCS_BUCKET_NAME``
        environment variable.
        """
        self.logs_dir: str = "logs"
        self.screenshots_dir: str = os.path.join("logs", "screenshots")
        self.actions_log: str = os.path.join("logs", "actions.json")
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self.gcs_client: Optional[Any] = None
        self.bucket: Optional[Any] = None
        if GCS_AVAILABLE and GCS_BUCKET:
            try:
                self.gcs_client = gcs.Client()
                self.bucket = self.gcs_client.bucket(GCS_BUCKET)
                logger.info("Google Cloud Storage connected: gs://%s", GCS_BUCKET)
            except Exception as exc:
                logger.warning("GCS unavailable, using local storage: %s", exc)

    def _upload_to_gcs(
        self, blob_name: str, data: bytes, content_type: str = "image/png"
    ) -> bool:
        """Upload data to Google Cloud Storage.

        Best-effort upload that logs errors but does not raise exceptions.
        Returns success status for monitoring.

        Args:
            blob_name: The GCS object name (path within the bucket).
            data: Raw bytes to upload.
            content_type: MIME type of the data. Defaults to ``image/png``.

        Returns:
            True if the upload succeeded, False otherwise.
        """
        if not self.bucket:
            return False
        try:
            blob = self.bucket.blob(blob_name)
            blob.upload_from_string(data, content_type=content_type)
            logger.debug("Uploaded to GCS: gs://%s/%s", GCS_BUCKET, blob_name)
            return True
        except Exception as exc:
            logger.error("GCS upload failed for %s: %s", blob_name, exc)
            return False

    def save_screenshot(
        self, pil_image: Image.Image, timestamp: Optional[str] = None
    ) -> str:
        """Save a screenshot to local filesystem and GCS.

        Encodes the PIL Image as an optimized PNG file and writes it to
        both the local screenshots directory and the GCS bucket.

        Args:
            pil_image: The screenshot to save as a PIL Image.
            timestamp: Optional timestamp string for the filename. If not
                provided, the current time is used. Format: ``YYYYMMDD_HHMMSS``.

        Returns:
            Local filesystem path of the saved screenshot, or an empty
            string if the save failed.
        """
        try:
            if not timestamp:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_ts: str = timestamp.replace(":", "-").replace(" ", "_")

            buf = BytesIO()
            pil_image.save(buf, format="PNG", optimize=True)
            png_bytes: bytes = buf.getvalue()

            # Local save
            path: str = os.path.join(self.screenshots_dir, f"{safe_ts}.png")
            with open(path, "wb") as file_handle:
                file_handle.write(png_bytes)

            # GCS upload (best-effort)
            self._upload_to_gcs(f"screenshots/{safe_ts}.png", png_bytes, "image/png")

            logger.debug("Screenshot saved: %s (%d bytes)", path, len(png_bytes))
            return path
        except Exception as exc:
            logger.error("Screenshot save failed: %s", exc)
            return ""

    def save_action_log(self, action_dict: dict[str, Any]) -> None:
        """Save an action log entry to local JSONL file and GCS.

        Appends the action as a single JSON line to the local log file
        and uploads a copy to the GCS bucket organized by date.

        Args:
            action_dict: Dictionary containing the command, response,
                and context data to log.
        """
        try:
            action_dict["logged_at"] = datetime.now().isoformat()

            # Append-only local log (no full read-write)
            with open(self.actions_log, "a", encoding="utf-8") as file_handle:
                file_handle.write(json.dumps(action_dict) + "\n")

            # GCS upload as JSONL
            line: bytes = (json.dumps(action_dict) + "\n").encode("utf-8")
            ts: str = datetime.now().strftime("%Y%m%d")
            self._upload_to_gcs(
                f"logs/actions_{ts}.jsonl", line, "application/json"
            )
        except Exception as exc:
            logger.error("Action log save failed: %s", exc)

    def get_recent_screenshots(self, n: int = 5) -> list[str]:
        """Retrieve paths to the most recent local screenshots.

        Args:
            n: Maximum number of screenshot paths to return. Defaults to 5.

        Returns:
            List of absolute file paths to the most recent screenshots,
            sorted newest first. Returns an empty list if no screenshots
            exist or an error occurs.
        """
        try:
            files: list[str] = [
                os.path.join(self.screenshots_dir, f)
                for f in os.listdir(self.screenshots_dir)
                if f.endswith(".png")
            ]
            files.sort(key=os.path.getmtime, reverse=True)
            return files[:n]
        except (OSError, IOError):
            return []

    def health_check(self) -> dict[str, Any]:
        """Check storage backend health and return status.

        Returns:
            Dictionary with local storage status and GCS connectivity.
        """
        status: dict[str, Any] = {
            "local_storage": os.path.isdir(self.logs_dir),
            "screenshots_dir": os.path.isdir(self.screenshots_dir),
            "gcs_available": self.bucket is not None,
            "gcs_bucket": GCS_BUCKET if self.bucket else None,
        }
        return status
