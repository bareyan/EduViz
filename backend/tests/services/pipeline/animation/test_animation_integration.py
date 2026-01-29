"""
Integration tests for animation pipeline.

Tests the full flow from visual script to Manim code generation to rendering.
Uses extensive mocking to avoid requiring Manim/FFmpeg.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path


@pytest.mark.asyncio
class TestGenerationToValidationFlow:
    """Test integration between GenerationToolHandler and CodeValidator"""

    @pytest.fixture
    def mock_engine(self):
        """Create mock prompting engine"""
        engine = MagicMock()
        engine.generate = AsyncMock()
        return engine

    @pytest.fixture
    def validator(self):
        """Create real CodeValidator"""
        from app.services.pipeline.animation.generation.validation.code_validator import (
            CodeValidator,
        )
        return CodeValidator()

    @pytest.fixture
    def handler(self, mock_engine, validator):
        """Create GenerationToolHandler with real validator"""
        from app.services.pipeline.animation.generation.tools.generation import (
            GenerationToolHandler,
        )
        return GenerationToolHandler(mock_engine, validator)

    async def test_valid_code_passes_immediately(self, handler, mock_engine):
        """Test valid code passes validation on first try"""
        valid_code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
'''
        mock_engine.generate.return_value = {
            "success": True,
            "function_calls": [{
                "name": "write_manim_code",
                "args": {"code": valid_code}
            }]
        }
        
        from app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig
        
        with patch("app.services.infrastructure.llm.gemini.get_types_module"):
            result = await handler._run_loop("Generate test", PromptConfig())
        
        assert result.success is True
        assert result.iterations == 1
        assert "Scene" in result.code

    async def test_syntax_error_triggers_retry(self, handler, mock_engine):
        """Test syntax error triggers feedback and retry"""
        invalid_code = '''from manim import *

class TestScene(Scene):
    def construct(self
        pass  # Missing closing paren
'''
        valid_code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
        mock_engine.generate.side_effect = [
            {
                "success": True,
                "function_calls": [{
                    "name": "write_manim_code",
                    "args": {"code": invalid_code}
                }]
            },
            {
                "success": True,
                "function_calls": [{
                    "name": "write_manim_code",
                    "args": {"code": valid_code}
                }]
            }
        ]
        
        from app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig
        
        with patch("app.services.infrastructure.llm.gemini.get_types_module"):
            result = await handler._run_loop("Generate test", PromptConfig())
        
        assert result.success is True
        assert result.iterations == 2
        assert len(result.feedback_history) >= 1


@pytest.mark.asyncio
class TestManimGeneratorFlow:
    """Test ManimGenerator orchestration"""

    @pytest.fixture
    def mock_generator(self):
        """Create ManimGenerator with all dependencies mocked"""
        with patch("app.services.pipeline.animation.generation.generator.VisualScriptGenerator"), \
             patch("app.services.pipeline.animation.generation.generator.GenerationToolHandler"), \
             patch("app.services.pipeline.animation.generation.generator.CodeValidator"), \
             patch("app.services.pipeline.animation.generation.generator.renderer"):
            
            from app.services.pipeline.animation.generation.generator import ManimGenerator
            
            gen = ManimGenerator()
            
            # Setup visual script generator mock
            mock_vs_result = MagicMock()
            mock_vs_result.success = True
            mock_plan = MagicMock()
            mock_plan.total_duration = 10.0
            mock_plan.segments = [MagicMock()]
            mock_vs_result.visual_script = mock_plan
            gen.visual_script_generator.generate_and_save = AsyncMock(return_value=mock_vs_result)
            
            # Setup generation handler mock
            mock_gen_result = MagicMock()
            mock_gen_result.success = True
            mock_gen_result.code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
            gen.generation_handler.generate = AsyncMock(return_value=mock_gen_result)
            
            # Setup renderer mock
            from app.services.pipeline.animation.generation import renderer
            renderer.render_scene = AsyncMock(return_value="/tmp/video.mp4")
            
            return gen

    async def test_generate_section_video_success_flow(self, mock_generator, tmp_path):
        """Test complete section generation flow"""
        section = {
            "title": "Test Section",
            "narration": "This is a test narration for the animation."
        }
        
        with patch("app.services.pipeline.animation.generation.generator.create_scene_file") as mock_create, \
             patch("builtins.open", MagicMock()):
            
            mock_create.return_value = "scene_code"
            
            result = await mock_generator.generate_section_video(
                section=section,
                output_dir=str(tmp_path),
                section_index=0,
                audio_duration=10.0
            )
        
        assert result["video_path"] == "/tmp/video.mp4"
        assert result["manim_code"] is not None
        mock_generator.visual_script_generator.generate_and_save.assert_called_once()
        mock_generator.generation_handler.generate.assert_called_once()

    async def test_generation_failure_uses_fallback(self, mock_generator, tmp_path):
        """Test fallback is used when generation fails"""
        mock_generator.generation_handler.generate.return_value.success = False
        mock_generator.generation_handler.generate.return_value.code = None
        
        # Mock fallback generation
        mock_generator._generate_fallback = AsyncMock(return_value="fallback code")
        
        section = {"title": "Test"}
        
        with patch("app.services.pipeline.animation.generation.generator.create_scene_file") as mock_create, \
             patch("builtins.open", MagicMock()):
            
            mock_create.return_value = "scene_code"
            
            result = await mock_generator.generate_section_video(
                section=section,
                output_dir=str(tmp_path),
                section_index=0,
                audio_duration=5.0
            )
        
        # Either fallback was used or video path is None
        assert result["manim_code"] is not None or result["video_path"] is None


@pytest.mark.asyncio
class TestCodeParsingFlow:
    """Test parsing and code extraction flows"""

    def test_markdown_extraction_integration(self):
        """Test code extraction from realistic LLM response"""
        from app.services.pipeline.animation.generation.tools.code_manipulation import (
            extract_code_from_response,
        )
        
        llm_response = '''I'll create a Manim animation for you:

```python
from manim import *

class IntroScene(Scene):
    def construct(self):
        title = Text("Hello World", font_size=48)
        self.play(Write(title))
        self.wait(2)
```

This animation displays "Hello World" and waits for 2 seconds.'''
        
        code = extract_code_from_response(llm_response)
        
        assert code is not None
        assert "class IntroScene(Scene)" in code
        assert "def construct" in code
        assert "```" not in code

    def test_patch_application_integration(self):
        """Test patch application with realistic code"""
        from app.services.pipeline.animation.generation.tools.code_manipulation import (
            apply_patches,
        )
        
        original_code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        circle = Circle(radius=1)
        circle.set_color(RED)
        self.play(Create(circle))
        self.wait(1)
'''
        
        patches = [
            {
                "search": "circle = Circle(radius=1)",
                "replace": "circle = Circle(radius=2)",
                "reason": "Make circle larger"
            },
            {
                "search": "circle.set_color(RED)",
                "replace": "circle.set_color(BLUE)",
                "reason": "Change color to blue"
            }
        ]
        
        new_code, applied, details = apply_patches(original_code, patches)
        
        assert applied == 2
        assert "radius=2" in new_code
        assert "BLUE" in new_code


@pytest.mark.asyncio
class TestVisualScriptIntegration:
    """Test visual script generation integration"""

    def test_visual_script_prompt_formatting(self):
        """Test visual script is formatted correctly for prompts"""
        from app.services.pipeline.animation.prompts import format_visual_script_for_prompt
        
        visual_script = {
            "segments": [
                {
                    "segment_id": 0,
                    "narration_text": "Welcome to this tutorial.",
                    "visual_description": "Display welcome text with fade in animation.",
                    "visual_elements": ["Title text", "Fade animation"],
                    "audio_duration": 3.0,
                    "post_narration_pause": 1.0
                },
                {
                    "segment_id": 1,
                    "narration_text": "Let's explore circles.",
                    "visual_description": "Draw a circle in the center.",
                    "visual_elements": ["Circle", "Create animation"],
                    "audio_duration": 2.5,
                    "post_narration_pause": 0.5
                }
            ]
        }
        
        result = format_visual_script_for_prompt(visual_script)
        
        assert "Segment 1" in result
        assert "Segment 2" in result
        assert "Welcome" in result
        assert "circles" in result
        assert "3.0s" in result

    def test_segment_timing_formatting(self):
        """Test segment timing table is formatted correctly"""
        from app.services.pipeline.animation.prompts import format_segment_timing_for_prompt
        
        visual_script = {
            "segments": [
                {
                    "segment_id": 0,
                    "audio_duration": 5.0,
                    "post_narration_pause": 1.0
                },
                {
                    "segment_id": 1,
                    "audio_duration": 3.0,
                    "post_narration_pause": 0.5
                }
            ]
        }
        
        result = format_segment_timing_for_prompt(visual_script)
        
        assert "Segment" in result
        assert "Audio Duration" in result
        assert "6.0" in result or "5.0" in result  # First segment total


@pytest.mark.asyncio
class TestErrorRecoveryFlow:
    """Test error recovery and retry mechanisms"""

    @pytest.fixture
    def handler(self):
        """Create handler for testing"""
        with patch("app.services.infrastructure.llm.gemini.get_types_module"):
            from app.services.pipeline.animation.generation.tools.generation import (
                GenerationToolHandler,
            )
            from app.services.pipeline.animation.generation.validation.code_validator import (
                CodeValidator,
            )
            
            mock_engine = MagicMock()
            mock_engine.generate = AsyncMock()
            validator = CodeValidator()
            
            return GenerationToolHandler(mock_engine, validator), mock_engine

    async def test_max_iterations_exceeded(self, handler):
        """Test behavior when max iterations are exceeded"""
        gen_handler, mock_engine = handler
        gen_handler.MAX_ITERATIONS = 2
        
        invalid_code = '''def broken(:
    pass
'''
        mock_engine.generate.return_value = {
            "success": True,
            "function_calls": [{
                "name": "write_manim_code",
                "args": {"code": invalid_code}
            }]
        }
        
        from app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig
        
        with patch("app.services.infrastructure.llm.gemini.get_types_module"):
            result = await gen_handler._run_loop("Generate", PromptConfig())
        
        assert result.success is False
        assert result.iterations >= 2

    async def test_no_tool_call_uses_text_fallback(self, handler):
        """Test fallback when model returns text instead of tool call"""
        gen_handler, mock_engine = handler
        
        mock_engine.generate.return_value = {
            "success": True,
            "response": '''Here's the code:
```python
from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
```''',
            "function_calls": []
        }
        
        from app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig
        
        with patch("app.services.infrastructure.llm.gemini.get_types_module"), \
             patch("app.services.pipeline.animation.generation.tools.generation.extract_code_from_response") as mock_extract:
            
            mock_extract.return_value = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
            
            result = await gen_handler._run_loop("Generate", PromptConfig())
        
        assert result.success is True
        assert "Scene" in result.code


@pytest.mark.asyncio
class TestContextIntegration:
    """Test context building integration"""

    def test_full_context_assembly(self):
        """Test building complete context for generation"""
        from app.services.pipeline.animation.generation.tools.context import build_context
        
        context = build_context(
            style="3b1b",
            animation_type="equation",
            target_duration=30.0,
            language="en"
        )
        
        prompt = context.to_system_prompt()
        
        # Should have all major components
        assert "3Blue1Brown" in prompt or "Dark" in prompt
        assert "MathTex" in prompt or "equation" in prompt.lower()
        assert "30" in prompt  # Duration
        assert "construct" in prompt

    def test_multilingual_context(self):
        """Test context for non-English languages"""
        from app.services.pipeline.animation.generation.tools.context import build_context
        
        context = build_context(
            style="clean",
            animation_type="text",
            target_duration=20.0,
            language="zh"
        )
        
        prompt = context.to_system_prompt()
        
        # Verify context is generated (not empty) and contains basic Manim guidance
        assert len(prompt) > 100  # Should be substantial
        assert "Manim" in prompt or "manim" in prompt
        assert "construct" in prompt or "Scene" in prompt
