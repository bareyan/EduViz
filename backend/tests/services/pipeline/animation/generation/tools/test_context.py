"""
Tests for app.services.pipeline.animation.generation.tools.context

Tests for Manim context, style configurations, and language settings.
"""

import pytest
from app.services.pipeline.animation.generation.tools.context import (
    build_context,
    get_style_config,
    get_style_instructions,
    get_theme_setup_code,
    get_animation_guidance,
    get_language_instructions,
    get_manim_reference,
    ManimContext,
    StyleConfig,
    STYLES,
    MANIM_VERSION,
    ANIMATION_GUIDANCE,
    LANGUAGE_CONFIGS,
)


class TestBuildContext:
    """Test suite for build_context function"""

    def test_returns_manim_context(self):
        """Test that build_context returns a ManimContext"""
        context = build_context()
        
        assert isinstance(context, ManimContext)

    def test_default_values(self):
        """Test default parameter values"""
        context = build_context()
        
        assert context.target_duration == 30.0
        assert context.language == "en"
        assert context.api_reference is not None
        assert context.style_instructions is not None
        assert context.animation_guidance is not None

    def test_custom_values(self):
        """Test custom parameter values"""
        context = build_context(
            style="clean",
            animation_type="equation",
            target_duration=60.0,
            language="es"
        )
        
        assert context.target_duration == 60.0
        assert context.language == "es"
        assert "Clean" in context.style_instructions or "clean" in context.style_instructions.lower()
        assert "equation" in context.animation_guidance.lower()


class TestGetStyleConfig:
    """Test suite for get_style_config function"""

    def test_returns_3b1b_by_default(self):
        """Test default style is 3b1b"""
        config = get_style_config("3b1b")
        
        assert isinstance(config, StyleConfig)
        assert config.name == "3Blue1Brown"
        assert config.background == "#1C1C1C"

    def test_clean_style(self):
        """Test clean style configuration"""
        config = get_style_config("clean")
        
        assert config.name == "Clean Light"
        assert config.background == "WHITE"
        assert config.text_color == "BLACK"

    def test_dracula_style(self):
        """Test dracula style configuration"""
        config = get_style_config("dracula")
        
        assert config.name == "Dracula"
        assert config.background == "#282a36"

    def test_unknown_style_returns_default(self):
        """Test unknown style returns 3b1b default"""
        config = get_style_config("nonexistent")
        
        assert config.name == "3Blue1Brown"


class TestGetStyleInstructions:
    """Test suite for get_style_instructions function"""

    def test_includes_style_name(self):
        """Test instructions include style name"""
        instructions = get_style_instructions("3b1b")
        
        assert "3Blue1Brown" in instructions

    def test_includes_background_info(self):
        """Test instructions mention background is pre-configured"""
        instructions = get_style_instructions("3b1b")
        
        assert "Background" in instructions or "background" in instructions

    def test_includes_color_palette(self):
        """Test instructions include color information"""
        instructions = get_style_instructions("3b1b")
        
        assert "BLUE" in instructions or "primary" in instructions.lower()


class TestGetThemeSetupCode:
    """Test suite for get_theme_setup_code function"""

    def test_3b1b_theme_code(self):
        """Test 3b1b theme generates correct background code"""
        code = get_theme_setup_code("3b1b")
        
        assert "self.camera.background_color" in code
        assert "1C1C1C" in code
        assert "3Blue1Brown" in code

    def test_clean_theme_code(self):
        """Test clean theme generates WHITE background"""
        code = get_theme_setup_code("clean")
        
        assert "self.camera.background_color" in code
        assert "WHITE" in code

    def test_dracula_theme_code(self):
        """Test dracula theme generates correct hex color"""
        code = get_theme_setup_code("dracula")
        
        assert "self.camera.background_color" in code
        assert "282a36" in code

    def test_unknown_theme_returns_default(self):
        """Test unknown theme returns default dark"""
        code = get_theme_setup_code("nonexistent")
        
        assert "self.camera.background_color" in code


class TestGetAnimationGuidance:
    """Test suite for get_animation_guidance function"""

    def test_equation_guidance(self):
        """Test equation animation guidance"""
        guidance = get_animation_guidance("equation")
        
        assert "MathTex" in guidance
        assert "ReplacementTransform" in guidance or "Transform" in guidance

    def test_text_guidance(self):
        """Test text animation guidance"""
        guidance = get_animation_guidance("text")
        
        assert "Text" in guidance
        assert "font_size" in guidance

    def test_diagram_guidance(self):
        """Test diagram animation guidance"""
        guidance = get_animation_guidance("diagram")
        
        assert "Circle" in guidance or "Arrow" in guidance or "Shape" in guidance

    def test_graph_guidance(self):
        """Test graph animation guidance"""
        guidance = get_animation_guidance("graph")
        
        assert "Axes" in guidance

    def test_code_guidance(self):
        """Test code animation guidance"""
        guidance = get_animation_guidance("code")
        
        assert "Code" in guidance or "Monospace" in guidance

    def test_unknown_type_returns_text_default(self):
        """Test unknown animation type returns text guidance"""
        guidance = get_animation_guidance("unknown_type")
        
        assert "Text" in guidance


class TestGetLanguageInstructions:
    """Test suite for get_language_instructions function"""

    def test_english_language(self):
        """Test English language instructions"""
        instructions = get_language_instructions("en")
        
        assert "English" in instructions

    def test_chinese_language_with_font(self):
        """Test Chinese language includes font specification"""
        instructions = get_language_instructions("zh")
        
        assert "Chinese" in instructions
        assert "Noto Sans SC" in instructions

    def test_arabic_language_rtl(self):
        """Test Arabic language includes RTL instructions"""
        instructions = get_language_instructions("ar")
        
        assert "Arabic" in instructions
        assert "right-to-left" in instructions

    def test_armenian_language(self):
        """Test Armenian language with font"""
        instructions = get_language_instructions("hy")
        
        assert "Armenian" in instructions
        assert "Noto Sans Armenian" in instructions

    def test_unknown_language_returns_english(self):
        """Test unknown language returns English default"""
        instructions = get_language_instructions("xx")
        
        assert "English" in instructions


class TestManimContext:
    """Test suite for ManimContext dataclass"""

    def test_to_system_prompt_format(self):
        """Test to_system_prompt returns formatted string"""
        context = build_context(
            style="3b1b",
            animation_type="text",
            target_duration=15.0,
            language="en"
        )
        
        prompt = context.to_system_prompt()
        
        assert isinstance(prompt, str)
        assert "15.0" in prompt or "15" in prompt
        assert "en" in prompt
        assert "construct()" in prompt

    def test_to_system_prompt_includes_api_reference(self):
        """Test system prompt includes API reference"""
        context = build_context()
        prompt = context.to_system_prompt()
        
        assert "UP" in prompt or "DOWN" in prompt  # Direction constants
        assert "self.play" in prompt or "FadeIn" in prompt


class TestConstants:
    """Test suite for module constants"""

    def test_manim_version_defined(self):
        """Test MANIM_VERSION is defined"""
        assert MANIM_VERSION is not None
        assert isinstance(MANIM_VERSION, str)

    def test_styles_dict_populated(self):
        """Test STYLES dictionary has expected keys"""
        assert "3b1b" in STYLES
        assert "clean" in STYLES
        assert "dracula" in STYLES

    def test_animation_guidance_populated(self):
        """Test ANIMATION_GUIDANCE has expected keys"""
        assert "equation" in ANIMATION_GUIDANCE
        assert "text" in ANIMATION_GUIDANCE
        assert "diagram" in ANIMATION_GUIDANCE
        assert "graph" in ANIMATION_GUIDANCE
        assert "code" in ANIMATION_GUIDANCE

    def test_language_configs_populated(self):
        """Test LANGUAGE_CONFIGS has expected keys"""
        assert "en" in LANGUAGE_CONFIGS
        assert "zh" in LANGUAGE_CONFIGS
        assert "ar" in LANGUAGE_CONFIGS
        assert "hy" in LANGUAGE_CONFIGS


class TestGetManimReference:
    """Test suite for get_manim_reference function"""

    def test_returns_api_reference(self):
        """Test returns the Manim API reference string"""
        reference = get_manim_reference()
        
        assert isinstance(reference, str)
        assert len(reference) > 100  # Should be substantial

    def test_includes_direction_constants(self):
        """Test reference includes direction constants"""
        reference = get_manim_reference()
        
        assert "UP" in reference
        assert "DOWN" in reference
        assert "LEFT" in reference
        assert "RIGHT" in reference

    def test_includes_color_constants(self):
        """Test reference includes color constants"""
        reference = get_manim_reference()
        
        assert "RED" in reference or "BLUE" in reference

    def test_includes_common_patterns(self):
        """Test reference includes common code patterns"""
        reference = get_manim_reference()
        
        assert "self.play" in reference or "Write" in reference
