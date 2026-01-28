"""
Tests for app.services.pipeline.animation.generation.generator
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.animation.generation.generator import ManimGenerator


@pytest.mark.asyncio
class TestManimGenerator:
    """Test Manim generation orchestration."""

    @pytest.fixture
    def generator(self):
        # Patch all dependencies where they are imported in the generator module
        with patch("app.services.pipeline.animation.generation.generator.VisualScriptGenerator"), \
             patch("app.services.pipeline.animation.generation.generator.GenerationToolHandler"), \
             patch("app.services.pipeline.animation.generation.generator.CodeValidator"), \
             patch("app.services.pipeline.animation.generation.generator.renderer"):
            
            gen = ManimGenerator()
            # Mock sub-components
            # visual_script_generator.generate_and_save returns a GenerationResult
            mock_vs_result = MagicMock()
            mock_vs_result.success = True
            mock_plan = MagicMock()
            mock_plan.total_duration = 5.0
            mock_plan.segments = [MagicMock()]
            mock_vs_result.visual_script = mock_plan
            gen.visual_script_generator.generate_and_save = AsyncMock(return_value=mock_vs_result)
            
            # generation_handler.generate returns a tool.GenerationResult
            mock_tool_result = MagicMock()
            mock_tool_result.success = True
            mock_tool_result.code = "class Anim(Scene): pass"
            gen.generation_handler.generate = AsyncMock(return_value=mock_tool_result)
            
            # Mock renderer functions
            # renderer.render_scene is async
            from app.services.pipeline.animation.generation import renderer
            renderer.render_scene = AsyncMock(return_value="path.mp4")
            
            return gen

    async def test_generate_section_video_success(self, generator):
        """Test full section video generation flow."""
        section = {"title": "Test", "narration": "Hello"}
        
        # Patch code helpers
        with patch("app.services.pipeline.animation.generation.generator.create_scene_file") as mock_create:
            mock_create.return_value = "scene.py"
            
            result = await generator.generate_section_video(
                section=section,
                output_dir="/tmp",
                section_index=1,
                audio_duration=5.0
            )
            
            assert result["video_path"] == "path.mp4"
            assert result["manim_code"] is not None
            generator.visual_script_generator.generate_and_save.assert_called_once()
            generator.generation_handler.generate.assert_called_once()

    async def test_render_from_code(self, generator):
        """Test rendering from existing code."""
        from app.services.pipeline.animation.generation import renderer
        
        with patch("app.services.pipeline.animation.generation.generator.create_scene_file") as mock_create:
            mock_create.return_value = "scene.py"
            
            # render_from_code is async
            result = await generator.render_from_code("code", "/tmp", 1)
            
            assert result == "path.mp4"
            renderer.render_scene.assert_called_once()

    async def test_generate_manim_code_failure_return_value(self, generator):
        """Test result when code generation fails (fallback also fails or returns None)."""
        generator.generation_handler.generate.return_value.success = False
        
        # Mock _generate_fallback to return a string, but make renderer fail
        generator._generate_fallback = AsyncMock(return_value="fallback code")
        from app.services.pipeline.animation.generation import renderer
        renderer.render_scene = AsyncMock(return_value=None)
        
        section = {"title": "Fail"}
        
        # Patch create_scene_file and open
        with patch("app.services.pipeline.animation.generation.generator.create_scene_file", return_value="code"), \
             patch("builtins.open", MagicMock()):
            
            result = await generator.generate_section_video(section, "/tmp", 1, 5.0)
            
            # ManimGenerator returns video_path=None on absolute failure after retries
            assert result["video_path"] is None
            assert result["manim_code"] is not None
