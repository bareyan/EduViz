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
            self.mock_engine = MagicMock()
            # Use AsyncMock for the async generate method
            self.mock_engine.generate = AsyncMock()
            mock_engine_class.return_value = self.mock_engine
            return TranslationService()

    async def test_translate_text_basic(self, service):
        """Test single text translation."""
        self.mock_engine.generate.return_value = {
            "success": True,
            "response": "Hello World"
        }
        
        result = await service._translate_text("Привет мир", "ru", "en")
        assert result == "Hello World"
        self.mock_engine.generate.assert_called_once()

    async def test_translate_list_batch(self, service):
        """Test batch translation of multiple items."""
        # The implementation uses text separator. 
        # Making sure the mock response matches what the parser expects.
        self.mock_engine.generate.return_value = {
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
        
        # Use side_effect to handle multiple calls to _translate_section_texts
        # 1. Document Title
        # 2. Section texts (title + narration)
        service._translate_section_texts = AsyncMock(side_effect=[
            ["T_Title"],
            ["T_SectionTitle", "T_Narration"]
        ])
        
        result = await service.translate_script(script, "ru", "en")
        
        assert result["title"] == "T_Title"
        assert result["sections"][0]["title"] == "T_SectionTitle"
        assert result["sections"][0]["narration"] == "T_Narration"
        # Note: visual_description is NOT currently translated by the service
        assert result["sections"][0]["visual_description"] == "Showing hello"

    def test_singleton(self):
        """Test get_translation_service singleton behavior."""
        with patch("app.services.infrastructure.llm.PromptingEngine"):
            # Clear singleton for testing
            from app.services.features.translation.translation_service import _translation_service
            import app.services.features.translation.translation_service as ts_mod
            ts_mod._translation_service = None
            
            s1 = get_translation_service()
            s2 = get_translation_service()
            assert s1 is s2
