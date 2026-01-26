
import sys
from unittest.mock import MagicMock
import pytest

# Global mocks for optional cloud dependencies
# This ensures tests run# Avoids ImportErrors if dependencies are missing in test env
sys.modules["google"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.aiplatform"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["vertexai"] = MagicMock()
sys.modules["vertexai.preview"] = MagicMock()
sys.modules["vertexai.preview.generative_models"] = MagicMock()

@pytest.fixture(autouse=True)
def mock_cloud_env(monkeypatch):
    """Automatically mock cloud environment variables for all tests"""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/tmp/mock-creds.json")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
