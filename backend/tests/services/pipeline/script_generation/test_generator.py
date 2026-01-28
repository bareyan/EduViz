"""
Tests for app.services.pipeline.script_generation.generator
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.script_generation.generator import ScriptGenerator


@pytest.mark.asyncio
class TestScriptGenerator:
    """Test ScriptGenerator orchestration."""

    @pytest.fixture
    def generator(self):
        # Patch all sub-generators and infrastructure
        with patch("app.services.pipeline.script_generation.generator.PromptingEngine"), \
             patch("app.services.pipeline.script_generation.generator.BaseScriptGenerator"), \
             patch("app.services.pipeline.script_generation.generator.OutlineBuilder"), \
             patch("app.services.pipeline.script_generation.generator.SectionGenerator"), \
             patch("app.services.pipeline.script_generation.generator.OverviewGenerator"):
            
            gen = ScriptGenerator()
            # Set AsyncMocks for sub-generators
            gen.base.extract_content = AsyncMock(return_value="Extracted content")
            gen.base.chars_per_second = 15
            gen.outline_builder.build_outline = AsyncMock(return_value={"title": "Outline"})
            gen.section_generator.generate_sections = AsyncMock(return_value=[{"narration": "Hello"}])
            gen.section_generator.segment_narrations = MagicMock(side_effect=lambda x: x)
            gen.overview_generator.generate_overview_script = AsyncMock(return_value={"sections": [{"narration": "Overview"}]})
            
            # Mock language engine
            gen.lang_engine.generate = AsyncMock(return_value={"success": True, "response": "en"})
            
            return gen

    async def test_generate_script_comprehensive(self, generator):
        """Test comprehensive script generation orchestration."""
        topic = {"title": "Math"}
        result = await generator.generate_script("path.pdf", topic)
        
        assert result["mode"] == "comprehensive"
        assert result["script"]["title"] == "Outline"
        assert len(result["script"]["sections"]) == 1
        generator.outline_builder.build_outline.assert_called_once()
        generator.section_generator.generate_sections.assert_called_once()

    async def test_generate_script_overview(self, generator):
        """Test overview script generation orchestration."""
        topic = {"title": "Math"}
        result = await generator.generate_script("path.pdf", topic, video_mode="overview")
        
        assert result["mode"] == "overview"
        assert result["script"]["sections"][0]["narration"] == "Overview"
        generator.overview_generator.generate_overview_script.assert_called_once()
        # Should NOT call comprehensive generators
        generator.outline_builder.build_outline.assert_not_called()

    async def test_detect_language(self, generator):
        """Test language detection logic."""
        generator.lang_engine.generate.return_value = {"success": True, "response": " fr "}
        lang = await generator._detect_language("sample")
        assert lang == "fr"

    async def test_detect_language_fallback(self, generator):
        """Test failure fallback in language detection."""
        generator.lang_engine.generate.return_value = {"success": False}
        lang = await generator._detect_language("sample")
        assert lang == "en"
