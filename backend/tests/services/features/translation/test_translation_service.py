"""
Tests for app.services.features.translation.translation_service
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.features.translation.translation_service import TranslationService, get_translation_service


@pytest.mark.asyncio
class TestTranslationService:
    """Test TranslationService logic."""

    @pytest.fixture
    def service(self):
        # Patch PromptingEngine which is imported locally in __init__
        with patch("app.services.infrastructure.llm.PromptingEngine") as mock_engine_class:
            mock_engine = MagicMock()
            # Use AsyncMock for the async generate method
            mock_engine.generate = AsyncMock()
            mock_engine_class.return_value = mock_engine
            
            svc = TranslationService()
            svc.mock_engine = mock_engine  # Attach for access in tests
            return svc

    async def test_translate_text_basic(self, service):
        """Test single text translation."""
        service.mock_engine.generate.return_value = {
            "success": True,
            "response": "Hello World"
        }
        
        result = await service._translate_text("Привет мир", "ru", "en")
        assert result == "Hello World"
        service.mock_engine.generate.assert_called_once()

    async def test_translate_list_batch(self, service):
        """Test batch translation of multiple items."""
        # The implementation uses text separator. 
        # Making sure the mock response matches what the parser expects.
        service.mock_engine.generate.return_value = {
            "success": True,
            "response": "Apple \n---ITEM---\n Banana"
        }
        
        items = ["Яблоко", "Банан"]
        result = await service._translate_list(items, "ru", "en")
        
        assert result == ["Apple", "Banana"]

    def test_convert_latex_to_spoken(self, service):
        """Test LaTeX to spoken form conversion."""
        # Using double backslashes for LaTeX in raw strings or escaped strings
        text = "The integral $\\int_0^\\pi \\sin(x) dx$ is equal to 2."
        result = service._convert_latex_to_spoken(text)
        
        assert "$" not in result
        assert "integral" in result.lower()

    async def test_translate_manim_code(self, service):
        """Test translation of Text() strings in Manim code."""
        code = 'Text("Hello"), Circle(), Text("World")'
        
        with patch.object(service, "_translate_manim_texts", AsyncMock(return_value=["Привет", "Мир"])):
            result = await service.translate_manim_code(code, "ru")
            assert 'Text("Привет")' in result
            assert 'Text("Мир")' in result
            assert 'Circle()' in result

    async def test_translate_script_structure(self, service):
        """Test that script structure is preserved during translation."""
        script = {
            "title": "Script Title",
            "sections": [
                {
                    "title": "Section Title",
                    "narration": "Hello", 
                    "visual_description": "Showing hello"
                }
            ]
        }
        
        service._translate_section_texts = AsyncMock(side_effect=[
            ["T_Title"],
            ["T_SectionTitle", "T_Narration"]
        ])
        
        result = await service.translate_script(script, "ru", "en")
        
        assert result["title"] == "T_Title"
        assert result["sections"][0]["title"] == "T_SectionTitle"
        assert result["sections"][0]["narration"] == "T_Narration"

    async def test_convert_tex_for_non_latin(self, service):
        """Test conversion of mixed Tex() to Text/MathTex for non-Latin languages."""
        # Case 1: Simple Tex with only text
        code_simple = 't1 = Tex("Hello World", font_size=24)'
        result = await service._convert_tex_for_non_latin(code_simple, "bn", "en")
        assert 't1 = Text("Hello World", font_size=24)' in result
        
        # Case 2: Tex with math only
        code_math = 'm1 = Tex("$x^2 + y^2 = z^2$")'
        result = await service._convert_tex_for_non_latin(code_math, "bn", "en")
        assert 'm1 = MathTex(r"x^2 + y^2 = z^2")' in result

        # Case 3: Mixed content
        code_mixed = 'mix = Tex("Value of $x$ is good")'
        result = await service._convert_tex_for_non_latin(code_mixed, "bn", "en")
        
        assert 'VGroup(' in result
        assert 'Text(' in result
        assert 'MathTex(r"x")' in result
        assert '.arrange(' in result

    async def test_translate_section_texts_parsing(self, service):
        """Test correct parsing of batched translations in _translate_section_texts."""
        texts = ["Narration one", "Narration two"]
        
        # Mock engine response with expected format
        mock_response = """
[TEXT_0]
Perevod odin
[/TEXT_0]

[TEXT_1]
Perevod dva
[/TEXT_1]
"""
        service.mock_engine.generate.return_value = {"success": True, "response": mock_response}
        
        translated = await service._translate_section_texts(texts, "en", "ru")
        
        assert len(translated) == 2
        assert translated[0] == "Perevod odin"
        assert translated[1] == "Perevod dva"

    async def test_translate_manim_code_non_latin(self, service):
        """Test full Manim translation flow for non-Latin language (requiring Tex conversion)."""
        code = 'title = Tex("Start $x$ End")'
        
        # First, _convert_tex_for_non_latin will turn this into VGroup with Text("Start "), MathTex("x"), Text(" End")
        # Then _translate_manim_texts will translate the Text() parts
        
        # We need to mock _translate_manim_texts to handle the newly created Text objects
        service._translate_manim_texts = AsyncMock(return_value=["Nachalo ", " Konets"])
        
        result = await service.translate_manim_code(code, "ru")
        
        # Check that we have a VGroup (result of conversion)
        assert "VGroup" in result
        # Check that we have translated text (partial match because of font_size args)
        assert 'Text("Nachalo "' in result
        assert 'Text(" Konets"' in result 
        # Check that math is preserved
        assert 'MathTex(r"x")' in result

    def test_singleton(self):
        """Test get_translation_service singleton behavior."""
        with patch("app.services.infrastructure.llm.PromptingEngine"):
            from app.services.features.translation.translation_service import _translation_service
            import app.services.features.translation.translation_service as ts_mod
            # Save original
            original = ts_mod._translation_service
            ts_mod._translation_service = None
            
            try:
                s1 = get_translation_service()
                s2 = get_translation_service()
                assert s1 is s2
            finally:
                # Restore original
                ts_mod._translation_service = original
