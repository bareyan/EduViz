"""
Tests for app.services.infrastructure.llm.prompting_engine.base_engine
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.infrastructure.llm.prompting_engine.base_engine import PromptingEngine, PromptConfig


@pytest.mark.asyncio
class TestPromptingEngine:
    """Test PromptingEngine functionality."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Setup global patches for all tests in this class."""
        with patch("app.services.infrastructure.llm.prompting_engine.base_engine.create_client") as self.mock_create_client, \
             patch("app.services.infrastructure.llm.prompting_engine.base_engine.get_model_config") as self.mock_get_model_config, \
             patch("app.services.infrastructure.llm.prompting_engine.base_engine.get_thinking_config") as self.mock_get_thinking_config:
            
            self.client = MagicMock()
            self.mock_create_client.return_value = self.client
            self.mock_get_model_config.return_value = MagicMock(model_name="test-model")
            self.mock_get_thinking_config.return_value = None
            self.client._types_module = MagicMock()
            
            yield

    @pytest.fixture
    def engine(self):
        return PromptingEngine(config_key="test_key")

    async def test_generate_success(self, engine):
        """Test successful generation."""
        mock_response = MagicMock()
        mock_response.text = "Hello"
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 15
        
        self.client.models.generate_content.return_value = mock_response
        
        result = await engine.generate("Say hello")
        
        assert result["success"] is True
        assert result["response"] == "Hello"
        assert result["usage"]["input_tokens"] == 10
        self.client.models.generate_content.assert_called_once()

    async def test_generate_retry_on_failure(self, engine):
        """Test that generate retries on exception."""
        self.client.models.generate_content.side_effect = [
            Exception("First fail"),
            MagicMock(text="Second Success")
        ]
        
        config = PromptConfig(max_retries=2)
        with patch("asyncio.sleep", return_value=None):
            result = await engine.generate("Retry test", config=config)
            
            assert result["success"] is True
            assert result["response"] == "Second Success"
            assert self.client.models.generate_content.call_count == 2

    async def test_generate_timeout(self, engine):
        """Test timeout handling."""
        async def slow_call(*args, **kwargs):
            await asyncio.sleep(1)
            return MagicMock()
            
        self.client.models.generate_content.side_effect = slow_call
        
        config = PromptConfig(timeout=0.01, max_retries=1)
        result = await engine.generate("Too slow", config=config)
        
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    async def test_generate_json_parsing(self, engine):
        """Test JSON response parsing."""
        mock_response = MagicMock()
        mock_response.text = '{"key": "value"}'
        self.client.models.generate_content.return_value = mock_response
        
        config = PromptConfig(response_format="json")
        result = await engine.generate("Get JSON", config=config)
        
        assert result["success"] is True
        assert result["parsed_json"] == {"key": "value"}

    def test_generate_sync(self, engine):
        """Test synchronous wrapper."""
        engine.generate = AsyncMock(return_value={"success": True, "response": "Sync!"})
        
        result = engine.generate_sync("Sync prompt")
        assert result["response"] == "Sync!"
        engine.generate.assert_called_once()
