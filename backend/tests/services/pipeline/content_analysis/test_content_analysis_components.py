"""
Tests for app.services.pipeline.content_analysis components: Text, Image, and Main Analyzer
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.pipeline.content_analysis.text import TextAnalyzer
from app.services.pipeline.content_analysis.image import ImageAnalyzer
from app.services.pipeline.content_analysis.analyzer import MaterialAnalyzer


@pytest.mark.asyncio
class TestTextAnalyzer:
    """Test TextAnalyzer functionality."""

@pytest.mark.asyncio
class TestTextAnalyzer:
    """Test TextAnalyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        # Patch where it is imported in the base module
        with patch("app.services.pipeline.content_analysis.base.PromptingEngine") as mock_engine_cls, \
             patch("app.services.infrastructure.llm.prompting_engine.prompts.base.PromptTemplate.format", return_value="TEST_PROMPT"):
            
            mock_engine = MagicMock()
            mock_engine.generate = AsyncMock()
            mock_engine_cls.return_value = mock_engine
            return TextAnalyzer()

    async def test_analyze_success(self, analyzer, tmp_path):
        """Test successful text analysis."""
        # Setup input file
        text_file = tmp_path / "content.txt"
        text_file.write_text("Hello " * 1000, encoding="utf-8") # Create reasonable content
        
        # Setup mock response
        analyzer.engine.generate.return_value = {
            "success": True, 
            "response": '{"summary": "A great text", "suggested_topics": []}'
        }
        
        result = await analyzer.analyze(str(text_file), "file-1")
        
        assert result["file_id"] == "file-1"
        assert result["material_type"] == "text"
        assert result["summary"] == "A great text"
        assert result["total_content_pages"] >= 1
        
        # Verify generate called
        analyzer.engine.generate.assert_called_once()
        call_kwargs = analyzer.engine.generate.call_args[1]
        assert "response_schema" in call_kwargs

    async def test_analyze_empty_response(self, analyzer, tmp_path):
        """Test handling of empty/failed generation."""
        text_file = tmp_path / "empty.txt"
        text_file.write_text("Stuff")
        
        analyzer.engine.generate.return_value = {"success": False}
        
        result = await analyzer.analyze(str(text_file), "file-fail")
        
        assert result["file_id"] == "file-fail"
        assert isinstance(result, dict)


@pytest.mark.asyncio
class TestImageAnalyzer:
    """Test ImageAnalyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        # Patch where it is imported in the base module
        with patch("app.services.pipeline.content_analysis.base.PromptingEngine") as mock_engine_cls, \
             patch("app.services.infrastructure.llm.prompting_engine.prompts.base.PromptTemplate.format", return_value="TEST_PROMPT"):
            mock_engine = MagicMock()
            mock_engine.generate = AsyncMock()
            mock_engine.types = MagicMock()
            mock_engine_cls.return_value = mock_engine
            return ImageAnalyzer()

    async def test_analyze_png(self, analyzer, tmp_path):
        """Test PNG analysis."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"fake_png_data")
        
        analyzer.engine.generate.return_value = {
            "success": True, 
            "response": '{"summary": "An image", "detected_math_elements": 0}'
        }
        
        # Mock Part creation
        analyzer.engine.types.Part.from_data.return_value = "part_obj"
        
        result = await analyzer.analyze(str(img_file), "img-1")
        
        assert result["material_type"] == "image"
        assert result["summary"] == "An image"
        
        # Verify correct part creation
        analyzer.engine.types.Part.from_data.assert_called_with(
            data=b"fake_png_data", mime_type="image/png"
        )

    async def test_analyze_fallback(self, analyzer, tmp_path):
        """Test fallback if from_data doesn't exist (Gemini API vs Vertex)."""
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"fake_jpg")
        
        analyzer.engine.generate.return_value = {"success": True, "response": "{}"}
        
        # Simulate AttributeError on from_data
        analyzer.engine.types.Part.from_data.side_effect = AttributeError
        analyzer.engine.types.Part.from_bytes.return_value = "part_fallback"
        
        await analyzer.analyze(str(img_file), "img-2")
        
        analyzer.engine.types.Part.from_bytes.assert_called_with(
            data=b"fake_jpg", mime_type="image/jpeg"
        )


@pytest.mark.asyncio
class TestMaterialAnalyzer:
    """Test routing logic of MaterialAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        with patch("app.services.pipeline.content_analysis.analyzer.PDFAnalyzer") as mock_pdf, \
             patch("app.services.pipeline.content_analysis.analyzer.ImageAnalyzer") as mock_img, \
             patch("app.services.pipeline.content_analysis.analyzer.TextAnalyzer") as mock_txt:
            
            mock_pdf.return_value.analyze = AsyncMock(return_value="pdf_res")
            mock_img.return_value.analyze = AsyncMock(return_value="img_res")
            mock_txt.return_value.analyze = AsyncMock(return_value="txt_res")
            
            return MaterialAnalyzer()

    async def test_route_pdf(self, analyzer):
        res = await analyzer.analyze("file.pdf", "1")
        assert res == "pdf_res"
        analyzer.pdf_analyzer.analyze.assert_called_with("file.pdf", "1")

    async def test_route_image(self, analyzer):
        res = await analyzer.analyze("file.PNG", "2")
        assert res == "img_res"
        analyzer.image_analyzer.analyze.assert_called_with("file.PNG", "2")

    async def test_route_text(self, analyzer):
        res = await analyzer.analyze("file.tex", "3")
        assert res == "txt_res"
        analyzer.text_analyzer.analyze.assert_called_with("file.tex", "3")

    async def test_unsupported_file(self, analyzer):
        with pytest.raises(ValueError) as exc:
            await analyzer.analyze("file.mp4", "4")
        assert "Unsupported file type" in str(exc.value)
