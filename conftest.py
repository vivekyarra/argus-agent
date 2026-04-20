"""Root-level pytest configuration and shared fixtures.

Provides project-wide fixtures for tests including mock images,
base64 data, temporary directories, and patched service dependencies.
Automatically configures environment variables for test isolation.
"""

import base64
import os
import sys
from io import BytesIO
from typing import Generator
from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set test environment variables before any imports
os.environ.setdefault("GEMINI_API_KEY", "test-key-mock")
os.environ.setdefault("GCS_BUCKET_NAME", "test-bucket")
os.environ.setdefault("GCP_PROJECT_ID", "test-project")
os.environ.setdefault("ARGUS_API_KEY", "")
os.environ.setdefault("CORS_ORIGINS", "*")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "1000")
