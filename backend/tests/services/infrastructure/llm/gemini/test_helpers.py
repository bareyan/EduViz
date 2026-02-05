"""
Tests for app.services.infrastructure.llm.gemini.helpers
"""

import pytest
from unittest.mock import MagicMock
from app.services.infrastructure.llm.gemini.helpers import (
    generate_content_with_text,
    generate_content_with_images,
    generate_structured_output
)


@pytest.mark.asyncio
class TestGeminiHelpers:
    """Test Gemini helper functions."""

    @pytest.fixture
    def mock_client(self):
        client = MagicMock()
        client.models.generate_content = MagicMock()
        return client

    @pytest.fixture
    def mock_types(self):
        types = MagicMock()
        types.Content = MagicMock()
        types.Part = MagicMock()
        types.GenerateContentConfig = MagicMock()
        types.ThinkingConfig = MagicMock()
        return types

    async def test_generate_content_with_text_success(self, mock_client, mock_types):
        """Test successful text generation."""
        mock_response = MagicMock()
        mock_response.text = "Hello World"
        mock_client.models.generate_content.return_value = mock_response
        
        result = await generate_content_with_text(
            mock_client, "model-1", "HI", types_module=mock_types
        )
        
        assert result == "Hello World"
        mock_client.models.generate_content.assert_called_once()

    async def test_generate_content_with_text_thinking(self, mock_client, mock_types):
        """Test text generation with thinking config."""
        mock_client.models.generate_content.return_value = MagicMock(text="Res")
        
        await generate_content_with_text(
            mock_client, "model-1", "HI", 
            thinking_config={"thinking_level": "HIGH"},
            types_module=mock_types
        )
        
        mock_types.ThinkingConfig.assert_called_once_with(thinking_level="HIGH")

    async def test_generate_content_with_images(self, mock_client, mock_types):
        """Test multimodal generation."""
        mock_client.models.generate_content.return_value = MagicMock(text="Image Desk")
        
        image_data = [b"i1", b"i2"]
        result = await generate_content_with_images(
            mock_client, "model-multimodal", "Describe", 
            image_bytes_list=image_data,
            types_module=mock_types
        )
        
        assert result == "Image Desk"
        # Verify Part.from_data or Part.from_bytes was called
        assert mock_types.Part.from_data.called or mock_types.Part.from_bytes.called

    async def test_generate_structured_output(self, mock_client, mock_types):
        """Test JSON structured output."""
        mock_client.models.generate_content.return_value = MagicMock(text='{"ok": true}')
        schema = {"type": "object"}
        
        result = await generate_structured_output(
            mock_client, "model-json", "Get JSON",
            response_schema=schema,
            types_module=mock_types
        )
        
        assert result == '{"ok": true}'
        args, kwargs = mock_types.GenerateContentConfig.call_args
        assert kwargs["response_mime_type"] == "application/json"
        assert kwargs["response_schema"] == schema

    async def test_helper_failure_returns_none(self, mock_client, mock_types):
        """Test that exception in generation returns None."""
        mock_client.models.generate_content.side_effect = Exception("API Down")
        
        result = await generate_content_with_text(
            mock_client, "m", "p", types_module=mock_types
        )
        assert result is None

    async def test_cost_tracker_integration(self, mock_client, mock_types):
        """Verify cost tracker is called."""
        mock_tracker = MagicMock()
        mock_response = MagicMock(text="Res")
        mock_client.models.generate_content.return_value = mock_response
        
        await generate_content_with_text(
            mock_client, "m", "p", 
            cost_tracker=mock_tracker,
            types_module=mock_types
        )
        
        mock_tracker.track_usage.assert_called_once_with(mock_response, "m")
