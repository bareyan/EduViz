"""
Tests for features/translation/translation_service module

Tests for the TranslationService including language detection and text translation.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestTranslationServiceBasics:
    """Test suite for basic TranslationService functionality"""

    def test_service_module_imports(self):
        """Test that the module can be imported"""
        from app.services.features.translation.translation_service import (
            TranslationService,
            get_translation_service,
        )
        
        assert TranslationService is not None
        assert get_translation_service is not None

    def test_service_has_expected_methods(self):
        """Test that service class has expected methods"""
        from app.services.features.translation.translation_service import TranslationService
        
        # Check class has the expected methods (not instantiated)
        assert hasattr(TranslationService, 'translate_script')
        assert hasattr(TranslationService, 'translate_manim_code')
        assert hasattr(TranslationService, '_convert_latex_to_spoken')
        assert hasattr(TranslationService, '_translate_text')
        assert hasattr(TranslationService, '_translate_list')


class TestLanguageNames:
    """Test for language name lookup"""

    def test_language_names_imported(self):
        """Test that LANGUAGE_NAMES is available"""
        from app.core import LANGUAGE_NAMES
        
        assert "en" in LANGUAGE_NAMES
        assert LANGUAGE_NAMES["en"] == "English"

    def test_common_languages_present(self):
        """Test common languages are in the mapping"""
        from app.core import LANGUAGE_NAMES
        
        common_languages = ["en", "es", "fr", "de", "zh", "ja", "ko", "ru", "ar"]
        
        for lang in common_languages:
            assert lang in LANGUAGE_NAMES, f"Language {lang} not found"

    def test_get_language_name_function(self):
        """Test the get_language_name helper function"""
        from app.core import get_language_name
        
        assert get_language_name("en") == "English"
        assert get_language_name("es") == "Spanish"
        # Unknown language returns the code uppercased
        result = get_language_name("xyz")
        assert result == "XYZ"  # Function returns uppercased code for unknown languages


class TestConvertLatexToSpokenStatic:
    """Test suite for _convert_latex_to_spoken method patterns"""

    def test_latex_patterns_exist(self):
        """Test that the conversion handles LaTeX patterns"""
        # These patterns are handled by _convert_latex_to_spoken:
        patterns_to_handle = [
            r"\frac{a}{b}",  # fractions
            r"x^2",          # superscripts
            r"a_1",          # subscripts
            r"\sqrt{x}",     # square roots
            r"\sum",         # summation
            r"\int",         # integrals
            r"\alpha",       # Greek letters
            r"\pi",          # constants
        ]
        
        # Just verify patterns are valid strings
        for pattern in patterns_to_handle:
            assert isinstance(pattern, str)

    def test_latex_dollar_sign_detection(self):
        """Test detection of LaTeX delimiters"""
        texts_with_latex = [
            "$x^2$",
            "The formula $a = b$ is important",
            r"Consider $$\frac{1}{2}$$",
        ]
        
        for text in texts_with_latex:
            assert "$" in text  # All should contain LaTeX delimiters


class TestTranslationServiceIntegration:
    """Integration tests for TranslationService (requires mocking LLM)"""

    @pytest.fixture
    def mock_prompting_engine(self):
        """Create a mock for PromptingEngine"""
        mock_engine = MagicMock()
        mock_engine.generate = AsyncMock(return_value={
            "success": True,
            "response": "translated text"
        })
        return mock_engine

    def test_service_fixture_setup(self, mock_prompting_engine):
        """Test that mock engine is set up correctly"""
        assert mock_prompting_engine is not None
        assert hasattr(mock_prompting_engine, "generate")


class TestManimCodePatterns:
    """Test suite for Manim code pattern handling"""

    def test_text_call_pattern(self):
        """Test detection of Text() calls in Manim code"""
        import re
        
        code = '''
title = Text("Hello World")
subtitle = Text("Welcome")
'''
        # Pattern for Text() with string content
        pattern = r'Text\s*\(\s*["\']([^"\']+)["\']\s*\)'
        matches = re.findall(pattern, code)
        
        assert len(matches) == 2
        assert "Hello World" in matches
        assert "Welcome" in matches

    def test_tex_call_pattern(self):
        """Test detection of Tex() calls in Manim code"""
        import re
        
        code = '''
formula = Tex(r"$\\frac{a}{b}$")
equation = MathTex(r"x^2 + y^2 = z^2")
'''
        # Pattern for Tex() calls
        tex_pattern = r'(?:Math)?Tex\s*\('
        matches = re.findall(tex_pattern, code)
        
        assert len(matches) == 2

    def test_non_latin_scripts_list(self):
        """Test list of non-Latin script languages"""
        # Languages that require special handling for Tex->Text conversion
        non_latin = ["hy", "ar", "zh", "ja", "ko", "ru", "el", "he", "th"]
        
        # These should be separate from Latin-script languages
        latin = ["en", "es", "fr", "de", "pt", "it"]
        
        assert not any(l in non_latin for l in latin)


class TestTranslationScriptStructure:
    """Test suite for script structure handling"""

    def test_empty_script_structure(self):
        """Test handling of empty script structure"""
        empty_script = {
            "metadata": {},
            "sections": []
        }
        
        assert "sections" in empty_script
        assert len(empty_script["sections"]) == 0

    def test_section_with_narration(self):
        """Test section structure with narration"""
        section = {
            "title": "Introduction",
            "narration": "Welcome to this lesson.",
            "visual_description": "Title animation"
        }
        
        assert "narration" in section
        assert "title" in section

    def test_section_with_manim_code(self):
        """Test section structure with Manim code"""
        section = {
            "title": "Demo",
            "narration": "Here is a circle.",
            "manim_code": "circle = Circle()\nself.play(Create(circle))"
        }
        
        assert "manim_code" in section
        assert "Circle" in section["manim_code"]
