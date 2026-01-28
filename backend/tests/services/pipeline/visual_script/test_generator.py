"""
Tests for app.services.pipeline.visual_script.generator
"""

import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.visual_script.generator import VisualScriptGenerator, GenerationResult


@pytest.mark.asyncio
class TestVisualScriptGenerator:
    """Test Visual Script generation."""

    @pytest.fixture
    def generator(self):
        with patch("app.services.pipeline.visual_script.generator.PromptingEngine") as mock_engine_class:
            self.mock_engine = MagicMock()
            self.mock_engine.generate = AsyncMock()
            mock_engine_class.return_value = self.mock_engine
            return VisualScriptGenerator()

    async def test_generate_success(self, generator):
        """Test successful visual script generation."""
        section = {
            "title": "Introduction",
            "narration_segments": [{"text": "Hello", "duration": 2.0}]
        }
        
        # Generator expects raw JSON string in "response"
        mock_data = {
            "segments": [
                {
                    "segment_id": 0,
                    "narration_text": "Hello",
                    "visual_description": "Title Card fading in",
                    "visual_elements": ["Circle"],
                    "audio_duration": 2.0,
                    "post_narration_pause": 1.0
                }
            ],
            "total_duration": 3.0,
            "section_title": "Introduction"
        }
        
        self.mock_engine.generate.return_value = {
            "success": True,
            "response": json.dumps(mock_data)
        }
        
        # Patch utility function
        with patch("app.services.pipeline.visual_script.generator.build_audio_segments_from_section") as mock_bas:
            mock_bas.return_value = [{"text": "Hello", "duration": 2.0}]
            
            result = await generator.generate(section)
            
            assert result.success is True
            assert len(result.visual_script.segments) == 1
            # Total duration includes audio (2.0) + pause (1.0)
            assert result.visual_script.total_duration == 3.0

    async def test_generate_failure(self, generator):
        """Test handling of generation failure from LLM."""
        self.mock_engine.generate.return_value = {"success": False, "error": "Quota exceeded"}
        
        section = {"title": "X", "narration_segments": [{"text": "Hello"}]}
        with patch("app.services.pipeline.visual_script.generator.build_audio_segments_from_section", return_value=[{"text": "Hello", "duration": 2.0}]):
            result = await generator.generate(section)
            assert result.success is False
            assert "Quota exceeded" in result.error

    async def test_generate_and_save(self, generator, tmp_path):
        """Test generate_and_save orchestration."""
        section = {"title": "Test"}
        
        mock_plan = MagicMock()
        mock_plan.to_dict.return_value = {"segments": []}
        mock_plan.to_markdown.return_value = "# Test"
        
        with patch.object(generator, "generate", AsyncMock(return_value=GenerationResult(success=True, visual_script=mock_plan))):
            result = await generator.generate_and_save(section, str(tmp_path), 1)
            assert result.success is True
            assert (tmp_path / "visual_script_1.json").exists()
