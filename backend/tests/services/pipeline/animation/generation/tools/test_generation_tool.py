"""
Tests for app.services.pipeline.animation.generation.tools.generation
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.animation.generation.tools.generation import GenerationToolHandler, GenerationResult
from app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig


@pytest.mark.asyncio
class TestGenerationToolHandler:
    """Test the agentic generation loop."""

    @pytest.fixture
    def mock_engine(self):
        return MagicMock()

    @pytest.fixture
    def mock_validator(self):
        return MagicMock()

    @pytest.fixture
    def handler(self, mock_engine, mock_validator):
        return GenerationToolHandler(mock_engine, mock_validator)

    async def test_run_loop_success_first_try(self, handler, mock_engine, mock_validator):
        """Test success on first iteration with write_manim_code tool."""
        # Mock engine to return a function call
        mock_engine.generate = AsyncMock(return_value={
            "success": True,
            "function_calls": [
                {
                    "name": "write_manim_code",
                    "args": {"code": "class MyAnim(Scene): ..."}
                }
            ]
        })
        
        # Mock validator to return success
        mock_validator.validate_code.return_value = {"valid": True}
        
        # Patch recursive imports
        with patch("app.services.infrastructure.llm.gemini.get_types_module") as mock_get_types:
            mock_types = MagicMock()
            mock_get_types.return_value = mock_types
            
            config = PromptConfig(temperature=0.7)
            result = await handler._run_loop("Generate something", config)
            
            assert result.success is True
            assert result.code == "class MyAnim(Scene): ..."
            assert result.iterations == 1
            mock_validator.validate_code.assert_called_once_with("class MyAnim(Scene): ...")

    async def test_run_loop_retry_and_success(self, handler, mock_engine, mock_validator):
        """Test one failure then success after feedback."""
        # 1st response: invalid code
        # 2nd response: valid code
        mock_engine.generate = AsyncMock(side_effect=[
            {
                "success": True,
                "function_calls": [{"name": "write_manim_code", "args": {"code": "bad code"}}]
            },
            {
                "success": True,
                "function_calls": [{"name": "write_manim_code", "args": {"code": "good code"}}]
            }
        ])
        
        mock_validator.validate_code.side_effect = [
            {"valid": False, "error": "Syntax error"},
            {"valid": True}
        ]
        
        with patch("app.services.infrastructure.llm.gemini.get_types_module"):
            result = await handler._run_loop("prompt", PromptConfig())
            
            assert result.success is True
            assert result.code == "good code"
            assert result.iterations == 2
            assert "Syntax error" in result.feedback_history[0]

    async def test_run_loop_patch_failure_no_code(self, handler, mock_engine):
        """Test that patching without initial code fails/retries."""
        mock_engine.generate = AsyncMock(return_value={
            "success": True,
            "function_calls": [{"name": "patch_manim_code", "args": {"fixes": []}}]
        })
        
        handler.MAX_ITERATIONS = 1 # Stop early for test
        
        with patch("app.services.infrastructure.llm.gemini.get_types_module"):
            result = await handler._run_loop("prompt", PromptConfig())
            
            assert result.success is False
            assert "Cannot use patch_manim_code without existing code" in result.feedback_history[0]

    async def test_run_loop_text_fallback(self, handler, mock_engine, mock_validator):
        """Test fallback when model returns text instead of tool call."""
        mock_engine.generate = AsyncMock(return_value={
            "success": True,
            "response": "Here is your code:\n```python\nclass Fallback(Scene): ...\n```",
            "function_calls": []
        })
        
        mock_validator.validate_code.return_value = {"valid": True}
        
        # Patch extract_code_from_response locally in generation module
        with patch("app.services.pipeline.animation.generation.tools.generation.extract_code_from_response", return_value="class Fallback(Scene): ..."):
            with patch("app.services.infrastructure.llm.gemini.get_types_module"):
                result = await handler._run_loop("prompt", PromptConfig())
                
                assert result.success is True
                assert result.code == "class Fallback(Scene): ..."
