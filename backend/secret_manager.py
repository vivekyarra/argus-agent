"""Google Cloud Secret Manager integration for ARGUS.

Provides runtime secret retrieval from Google Cloud Secret Manager,
eliminating the need for secrets in environment variables or ``.env``
files in production. Falls back to environment variables when Secret
Manager is unavailable (local development).

Mitigates: OWASP A07:2021 — Identification and Authentication Failures
by ensuring secrets are never stored on disk in production environments.

Typical usage:
    from backend.secret_manager import get_secret

    api_key = get_secret("GEMINI_API_KEY")
    db_password = get_secret("DB_PASSWORD", default="dev-only")
"""

import logging
import os
from typing import Optional, Any

logger = logging.getLogger(__name__)

try:
    from google.cloud import secretmanager

    SECRET_MANAGER_AVAILABLE: bool = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False
    logger.info("google-cloud-secret-manager not installed; using env vars")

_client: Optional[Any] = None
_project_id: str = os.getenv("GCP_PROJECT_ID", "")


def _get_client() -> Optional[Any]:
    """Get or create a cached Secret Manager client.

    Returns:
        SecretManagerServiceClient instance, or None if unavailable.
    """
    global _client
    if _client is not None:
        return _client
    if not SECRET_MANAGER_AVAILABLE:
        return None
    try:
        _client = secretmanager.SecretManagerServiceClient()
        return _client
    except Exception as exc:
        logger.warning("Failed to create Secret Manager client: %s", exc)
        return None


def get_secret(
    secret_id: str,
    default: Optional[str] = None,
    version: str = "latest",
) -> Optional[str]:
    """Retrieve a secret from Google Cloud Secret Manager.

    Attempts to fetch the secret from Secret Manager first. If unavailable
    (library not installed, no credentials, or running locally), falls back
    to the corresponding environment variable.

    Args:
        secret_id: The secret name in Secret Manager (also used as the
            environment variable name for fallback).
        default: Default value if both Secret Manager and env var are
            unavailable. Defaults to None.
        version: Secret version to retrieve. Defaults to ``latest``.

    Returns:
        The secret value as a string, the environment variable value,
        or the default value.

    Example:
        >>> api_key = get_secret("GEMINI_API_KEY")
        >>> assert api_key is not None
    """
    # Try Secret Manager first
    client = _get_client()
    if client and _project_id:
        try:
            name = f"projects/{_project_id}/secrets/{secret_id}/versions/{version}"
            response = client.access_secret_version(request={"name": name})
            payload: str = response.payload.data.decode("UTF-8")
            logger.debug("Secret '%s' loaded from Secret Manager", secret_id)
            return payload
        except Exception as exc:
            logger.debug(
                "Secret '%s' not in Secret Manager: %s. Falling back to env.",
                secret_id,
                exc,
            )

    # Fallback to environment variable
    env_value: Optional[str] = os.getenv(secret_id)
    if env_value:
        return env_value

    return default


def list_secrets() -> list[str]:
    """List all available secret names in the configured project.

    Returns:
        List of secret resource names, or empty list if unavailable.
    """
    client = _get_client()
    if not client or not _project_id:
        return []
    try:
        parent = f"projects/{_project_id}"
        secrets = client.list_secrets(request={"parent": parent})
        return [s.name for s in secrets]
    except Exception as exc:
        logger.warning("Failed to list secrets: %s", exc)
        return []


def health_check() -> dict[str, object]:
    """Check Secret Manager connectivity and return status.

    Returns:
        Dictionary with availability status and project ID.
    """
    return {
        "available": SECRET_MANAGER_AVAILABLE and _get_client() is not None,
        "project_id": _project_id or "not configured",
        "library_installed": SECRET_MANAGER_AVAILABLE,
    }
