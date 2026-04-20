"""Test-specific fixtures for ARGUS test suite.

Provides reusable fixtures for mock images, base64 data, temporary
directories, patched Gemini API, and FastAPI test clients.
"""

import base64
import os
from io import BytesIO
from typing import Generator, Any
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample 640x480 RGB image for testing.

    Returns:
        PIL Image with a dark gray background.
    """
    return Image.new("RGB", (640, 480), color=(30, 30, 30))


@pytest.fixture
def sample_b64(sample_image: Image.Image) -> str:
    """Create a base64-encoded PNG from the sample image.

    Args:
        sample_image: The sample PIL Image fixture.

    Returns:
        Base64-encoded PNG string.
    """
    buf = BytesIO()
    sample_image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture
def large_image() -> Image.Image:
    """Create a large 2000x2000 image for size validation tests.

    Returns:
        PIL Image with a blue background.
    """
    return Image.new("RGB", (2000, 2000), color=(0, 0, 255))


@pytest.fixture
def oversized_image() -> Image.Image:
    """Create an oversized 5000x5000 image exceeding max dimensions.

    Returns:
        PIL Image exceeding the 4096x4096 limit.
    """
    return Image.new("RGB", (5000, 5000), color=(255, 0, 0))


@pytest.fixture
def mock_gemini() -> Generator[tuple[MagicMock, MagicMock], None, None]:
    """Patch Gemini API for isolated unit testing.

    Yields:
        Tuple of (mock_configure, mock_model_class) for assertion.
    """
    with patch("google.generativeai.configure") as mock_configure, \
         patch("google.generativeai.GenerativeModel") as mock_model:
        yield mock_configure, mock_model


@pytest.fixture
def mock_gcs() -> Generator[None, None, None]:
    """Patch Google Cloud Storage for isolated testing.

    Yields:
        None (patches are active during the test).
    """
    with patch("backend.storage.GCS_AVAILABLE", False), \
         patch("backend.storage.GCS_BUCKET", ""):
        yield


@pytest.fixture
def test_client(mock_gemini: tuple[MagicMock, MagicMock], mock_gcs: None) -> Any:
    """Create a FastAPI TestClient with mocked dependencies.

    Args:
        mock_gemini: Patched Gemini API fixture.
        mock_gcs: Patched GCS fixture.

    Returns:
        FastAPI TestClient instance.
    """
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)
