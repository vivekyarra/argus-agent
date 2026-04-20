"""Google Cloud Firestore integration for ARGUS.

Provides persistent storage of screen observations, action logs, and
session metadata using Cloud Firestore. Gracefully falls back to local-only
operation when Firestore credentials are not available.

Collections:
    observations: Screen analysis results with timestamps.
    actions: User command and response logs.
    sessions: Client connection session metadata.

Typical usage:
    from backend.firestore_client import FirestoreClient

    db = FirestoreClient()
    db.store_observation({"app_detected": "VSCode", "activity_summary": "Coding"})
    recent = db.get_recent_observations(limit=10)
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    logger.info("google-cloud-firestore not installed; Firestore disabled")


class FirestoreClient:
    """Client for Google Cloud Firestore operations.

    Manages CRUD operations for observations, actions, and sessions
    collections. Automatically initializes the Firestore client using
    application default credentials or the project ID from environment.

    Attributes:
        project_id: Google Cloud project ID for Firestore.
        db: Firestore client instance, or None if unavailable.
        available: Whether Firestore is connected and operational.
    """

    def __init__(self, project_id: Optional[str] = None) -> None:
        """Initialize the Firestore client.

        Args:
            project_id: GCP project ID. If not provided, reads from
                the ``GCP_PROJECT_ID`` environment variable or uses
                automatic detection on Cloud Run.
        """
        self.project_id: Optional[str] = project_id or os.getenv("GCP_PROJECT_ID", "")
        self.db: Optional[Any] = None
        self.available: bool = False
        self._connect()

    def _connect(self) -> None:
        """Establish connection to Firestore.

        Attempts to create a Firestore client. If credentials or the
        library are unavailable, sets ``available`` to False and logs
        the reason.
        """
        if not FIRESTORE_AVAILABLE:
            logger.warning("Firestore library not available")
            return
        try:
            if self.project_id:
                self.db = firestore.Client(project=self.project_id)
            else:
                self.db = firestore.Client()
            self.available = True
            logger.info("Firestore connected (project: %s)", self.project_id or "auto-detect")
        except Exception as exc:
            logger.warning("Firestore connection failed: %s", exc)
            self.available = False

    def store_observation(self, observation: dict[str, Any]) -> Optional[str]:
        """Store a screen observation in the ``observations`` collection.

        Args:
            observation: Dictionary containing observation data (app_detected,
                activity_summary, errors_seen, etc.).

        Returns:
            The Firestore document ID if stored successfully, None otherwise.
        """
        if not self.available or not self.db:
            return None
        try:
            observation["stored_at"] = datetime.utcnow().isoformat()
            doc_ref = self.db.collection("observations").add(observation)
            return doc_ref[1].id
        except Exception as exc:
            logger.error("Failed to store observation: %s", exc)
            return None

    def store_action(self, action: dict[str, Any]) -> Optional[str]:
        """Store an action log entry in the ``actions`` collection.

        Args:
            action: Dictionary containing command, response, and context data.

        Returns:
            The Firestore document ID if stored successfully, None otherwise.
        """
        if not self.available or not self.db:
            return None
        try:
            action["stored_at"] = datetime.utcnow().isoformat()
            doc_ref = self.db.collection("actions").add(action)
            return doc_ref[1].id
        except Exception as exc:
            logger.error("Failed to store action: %s", exc)
            return None

    def store_session(self, session_data: dict[str, Any]) -> Optional[str]:
        """Store a session metadata entry in the ``sessions`` collection.

        Args:
            session_data: Dictionary containing client connection metadata
                (IP, connect time, etc.).

        Returns:
            The Firestore document ID if stored successfully, None otherwise.
        """
        if not self.available or not self.db:
            return None
        try:
            session_data["created_at"] = datetime.utcnow().isoformat()
            doc_ref = self.db.collection("sessions").add(session_data)
            return doc_ref[1].id
        except Exception as exc:
            logger.error("Failed to store session: %s", exc)
            return None

    def get_recent_observations(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent observations ordered by storage time.

        Args:
            limit: Maximum number of observations to return. Defaults to 50.

        Returns:
            List of observation dictionaries, newest first.
        """
        if not self.available or not self.db:
            return []
        try:
            docs = (
                self.db.collection("observations")
                .order_by("stored_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as exc:
            logger.error("Failed to fetch observations: %s", exc)
            return []

    def get_recent_actions(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent action logs ordered by storage time.

        Args:
            limit: Maximum number of actions to return. Defaults to 50.

        Returns:
            List of action dictionaries, newest first.
        """
        if not self.available or not self.db:
            return []
        try:
            docs = (
                self.db.collection("actions")
                .order_by("stored_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as exc:
            logger.error("Failed to fetch actions: %s", exc)
            return []

    def get_observation_count(self) -> int:
        """Return the total number of stored observations.

        Returns:
            Total count of documents in the observations collection.
        """
        if not self.available or not self.db:
            return 0
        try:
            count_query = self.db.collection("observations").count()
            results = count_query.get()
            return results[0][0].value if results else 0
        except Exception as exc:
            logger.error("Failed to count observations: %s", exc)
            return 0

    def get_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve recent session metadata.

        Args:
            limit: Maximum number of sessions to return. Defaults to 20.

        Returns:
            List of session dictionaries, newest first.
        """
        if not self.available or not self.db:
            return []
        try:
            docs = (
                self.db.collection("sessions")
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as exc:
            logger.error("Failed to fetch sessions: %s", exc)
            return []

    def delete_old_observations(self, days: int = 30) -> int:
        """Delete observations older than the specified number of days.

        Args:
            days: Age threshold in days. Documents older than this are deleted.
                Defaults to 30.

        Returns:
            Number of documents deleted.
        """
        if not self.available or not self.db:
            return 0
        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            docs = (
                self.db.collection("observations")
                .where("stored_at", "<", cutoff)
                .stream()
            )
            deleted = 0
            for doc in docs:
                doc.reference.delete()
                deleted += 1
            logger.info("Deleted %d old observations (older than %d days)", deleted, days)
            return deleted
        except Exception as exc:
            logger.error("Failed to delete old observations: %s", exc)
            return 0

    def health_check(self) -> dict[str, Any]:
        """Check Firestore connectivity and return status information.

        Returns:
            Dictionary with availability status, project ID, and
            collection counts.
        """
        result: dict[str, Any] = {
            "available": self.available,
            "project_id": self.project_id or "auto-detect",
        }
        if self.available and self.db:
            try:
                result["observations_count"] = self.get_observation_count()
                result["status"] = "connected"
            except Exception:
                result["status"] = "error"
        else:
            result["status"] = "disconnected"
        return result
