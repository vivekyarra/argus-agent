"""Tests for the Firestore client module.

Tests Firestore CRUD operations, health checks, graceful degradation
when Firestore is unavailable, and data cleanup operations.
"""

import os
import sys
from unittest.mock import patch, MagicMock
from typing import Any

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFirestoreClient:
    """Tests for the FirestoreClient class."""

    def test_init_without_firestore_library(self) -> None:
        """Test graceful initialization when Firestore library is missing."""
        with patch("backend.firestore_client.FIRESTORE_AVAILABLE", False):
            from backend.firestore_client import FirestoreClient
            client = FirestoreClient.__new__(FirestoreClient)
            client.project_id = ""
            client.db = None
            client.available = False
            client._connect()
            assert client.available is False

    def test_store_observation_when_unavailable(self) -> None:
        """Test that store_observation returns None when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.store_observation({"app_detected": "test"})
        assert result is None

    def test_store_action_when_unavailable(self) -> None:
        """Test that store_action returns None when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.store_action({"command": "test"})
        assert result is None

    def test_store_session_when_unavailable(self) -> None:
        """Test that store_session returns None when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.store_session({"client_ip": "127.0.0.1"})
        assert result is None

    def test_get_recent_observations_when_unavailable(self) -> None:
        """Test that get_recent_observations returns empty list when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.get_recent_observations()
        assert result == []

    def test_get_recent_actions_when_unavailable(self) -> None:
        """Test that get_recent_actions returns empty list when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.get_recent_actions()
        assert result == []

    def test_health_check_disconnected(self) -> None:
        """Test health check reports disconnected status."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.project_id = "test-project"
        client.db = None
        client.available = False
        health = client.health_check()
        assert health["available"] is False
        assert health["status"] == "disconnected"

    def test_get_observation_count_when_unavailable(self) -> None:
        """Test observation count returns 0 when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        assert client.get_observation_count() == 0

    def test_get_sessions_when_unavailable(self) -> None:
        """Test that get_sessions returns empty list when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.get_sessions()
        assert result == []

    def test_delete_old_observations_when_unavailable(self) -> None:
        """Test that delete returns 0 when unavailable."""
        from backend.firestore_client import FirestoreClient
        client = FirestoreClient.__new__(FirestoreClient)
        client.db = None
        client.available = False
        result = client.delete_old_observations(days=30)
        assert result == 0

    @patch("backend.firestore_client.FIRESTORE_AVAILABLE", True)
    @patch("backend.firestore_client.firestore")
    def test_store_observation_with_mock_db(self, mock_firestore: MagicMock) -> None:
        """Test store_observation with a mocked Firestore client."""
        from backend.firestore_client import FirestoreClient

        mock_db = MagicMock()
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "test-doc-123"
        mock_db.collection.return_value.add.return_value = (None, mock_doc_ref)

        client = FirestoreClient.__new__(FirestoreClient)
        client.project_id = "test"
        client.db = mock_db
        client.available = True

        result = client.store_observation({"app_detected": "Chrome"})
        assert result == "test-doc-123"
        mock_db.collection.assert_called_with("observations")
