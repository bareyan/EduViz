
import sys
from unittest.mock import MagicMock

# Force mocks before ANY other imports
import os
os.environ["USE_VERTEX_AI"] = "false"
os.environ["GEMINI_API_KEY"] = "mock_key"
os.environ["GCP_PROJECT_ID"] = "mock_project"

# Patch dotenv to prevent loading .env file which overrides our mocks
try:
    import dotenv
    dotenv.load_dotenv = lambda *args, **kwargs: None
except ImportError:
    pass

print("Setting up global mocks for testing...")

# Mock google package hierarchy explicitly
google = MagicMock()
sys.modules["google"] = google

genai = MagicMock()
sys.modules["google.genai"] = genai
google.genai = genai

cloud = MagicMock()
sys.modules["google.cloud"] = cloud
google.cloud = cloud

aiplatform = MagicMock()
sys.modules["google.cloud.aiplatform"] = aiplatform
cloud.aiplatform = aiplatform

sys.modules["vertexai"] = MagicMock()
sys.modules["vertexai.preview"] = MagicMock()
sys.modules["vertexai.preview.generative_models"] = MagicMock()

# Also mock edge_tts and manim to be safe
sys.modules["edge_tts"] = MagicMock()
sys.modules["manim"] = MagicMock()

import pytest

if __name__ == "__main__":
    # Run pytest on the tests directory
    print("Running pytest on core...")
    sys.exit(pytest.main(["tests/core", "-vv"]))
