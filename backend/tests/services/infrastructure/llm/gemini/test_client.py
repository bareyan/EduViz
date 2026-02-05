"""
Tests for app.services.infrastructure.llm.gemini.client

Tests the UnifiedGeminiClient which handles both Gemini API and Vertex AI.
"""

import os
import sys
from unittest.mock import MagicMock, patch

# Ensure app is in path
sys.path.append(os.getcwd())

from app.services.infrastructure.llm.gemini.client import (
    UnifiedGeminiClient, 
    GenerationConfig,
    GeminiAPIModels,
    create_client
)

import inspect
print(f"[DEBUG] TEST sys.path: {sys.path}")
print(f"[DEBUG] UnifiedGeminiClient file: {inspect.getfile(UnifiedGeminiClient)}")

class TestGenerationConfig:
    def test_defaults(self):
        config = GenerationConfig()
        assert config.temperature == 1.0

class TestBackendDetection:
    @patch("app.services.infrastructure.llm.gemini.client.UnifiedGeminiClient._init_gemini_api")
    def test_detects_gemini_api(self, mock_init):
        with patch.dict(os.environ, {"USE_VERTEX_AI": "false"}):
            UnifiedGeminiClient(api_key="test-key")
            mock_init.assert_called_once_with("test-key")

    @patch("app.services.infrastructure.llm.gemini.client.UnifiedGeminiClient._init_vertex_ai")
    def test_detects_vertex_ai(self, mock_init):
        with patch.dict(os.environ, {"USE_VERTEX_AI": "true"}):
            UnifiedGeminiClient()
            mock_init.assert_called_once()


class TestGeminiAPIImplementation:
    def test_init_gemini_api_success(self):
        # Use context managers for unambiguous patching
        with patch.dict(os.environ, {"USE_VERTEX_AI": "false", "GEMINI_API_KEY": "test-key"}):
            # Patching Client and types on the module
            with patch("google.genai.Client"), \
                 patch("google.genai.types"):
                    with patch("vertexai.init"):
                        # Verify using the imported location which is what the code uses
                        from google import genai
                        # Clean up any calls from background tasks/other tests leaking into this mock
                        genai.Client.reset_mock()
                        
                        client = UnifiedGeminiClient()
                        
                        genai.Client.assert_called_once_with(api_key="test-key")
                    assert client.use_vertex_ai is False

    def test_generate_content_calls_backend(self):
        mock_backend = MagicMock()
        mock_backend.models = MagicMock()
        models = GeminiAPIModels(mock_backend)
        config = GenerationConfig(temperature=0.7)
        
        with patch("google.genai.types.GenerateContentConfig"):
            models.generate_content("model-1", "Prompt", config=config)
            mock_backend.models.generate_content.assert_called_once()

class TestVertexAIImplementation:
    def test_init_vertex_ai_success(self):
        with patch.dict(os.environ, {"GCP_PROJECT_ID": "p1", "GCP_LOCATION": "l1"}):
            with patch("vertexai.init") as mock_init:
                with patch("app.services.infrastructure.llm.gemini.client.VertexAIModels"), \
                     patch("app.services.infrastructure.llm.gemini.client.UnifiedGeminiClient._create_vertex_types_wrapper"):
                    client = MagicMock(spec=UnifiedGeminiClient)
                    UnifiedGeminiClient._init_vertex_ai(client)
                    mock_init.assert_called_once_with(project="p1", location="l1")

class TestConvenienceFunctions:
    @patch("app.services.infrastructure.llm.gemini.client.UnifiedGeminiClient")
    def test_create_client(self, mock_client):
        create_client(api_key="key")
        mock_client.assert_called_once_with(api_key="key")
