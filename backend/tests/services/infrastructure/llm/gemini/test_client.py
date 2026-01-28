"""
Tests for app.services.infrastructure.llm.gemini.client

Tests the UnifiedGeminiClient which handles both Gemini API and Vertex AI.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure app is in path
sys.path.append(os.getcwd())

from app.services.infrastructure.llm.gemini.client import (
    UnifiedGeminiClient, 
    GenerationConfig,
    GeminiAPIModels,
    VertexAIModels,
    create_client
)

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
        # Create a mock for the genai module
        mock_genai = MagicMock()
        # Put it in sys.modules so 'from google import genai' can find it
        # Actually, if it's 'from google import genai', we need 'google' to have 'genai'
        
        with patch("google.genai.Client") as mock_client_class:
            client = MagicMock(spec=UnifiedGeminiClient)
            UnifiedGeminiClient._init_gemini_api(client, "test-key")
            # If it failed to call, it might be due to how it's imported.
            # Let's try to verify if it even gets past the import.
            mock_client_class.assert_called()

    def test_generate_content_calls_backend(self):
        mock_backend = MagicMock()
        models = GeminiAPIModels(mock_backend)
        config = GenerationConfig(temperature=0.7)
        # We need to satisfy the 'from google.genai import types' inside the method
        with patch("google.genai.types.GenerateContentConfig") as mock_cfg:
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
