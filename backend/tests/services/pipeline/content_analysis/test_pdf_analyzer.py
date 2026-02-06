"""
Tests for app.services.pipeline.content_analysis.pdf
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.pipeline.content_analysis.pdf import PDFAnalyzer


@pytest.mark.asyncio
class TestPDFAnalyzer:
    """Test PDF extraction and Gemini analysis."""

    @pytest.fixture
    def mock_fitz(self):
        with patch("app.services.pipeline.content_analysis.pdf.fitz") as mock_f:
            yield mock_f

    @pytest.fixture
    def analyzer(self):
        # Patch BaseAnalyzer dependent services
        with patch("app.services.pipeline.content_analysis.base.PromptingEngine") as mock_engine_class, \
             patch("app.services.pipeline.content_analysis.base.get_model_config") as mock_cfg:
            
            mock_cfg.return_value = MagicMock(model_name="gemini-1.5-flash")
            self.mock_engine = MagicMock()
            self.mock_engine.generate = AsyncMock()
            mock_engine_class.return_value = self.mock_engine
            
            return PDFAnalyzer()

    async def test_analyze_success(self, analyzer, mock_fitz):
        """Test full PDF analysis flow."""
        # Mock PyMuPDF
        mock_doc = MagicMock()
        mock_fitz.open.return_value = mock_doc
        mock_doc.__len__.return_value = 2
        mock_page = MagicMock()
        mock_doc.__getitem__.side_effect = [mock_page, mock_page]
        mock_page.get_text.return_value = "Sample content"
        
        # Mock Gemini response
        self.mock_engine.generate.return_value = {
            "success": True,
            "response": '{"summary": "Test summary", "main_subject": "Math", "subject_area": "math", "key_concepts": [], "suggested_topics": [], "estimated_total_videos": 1}'
        }
        
        result = await analyzer.analyze("/fake/path.pdf", "file-123")
        
        assert result["file_id"] == "file-123"
        assert result["material_type"] == "pdf"
        assert result["total_content_pages"] == 2
        assert result["summary"] == "Test summary"
        mock_fitz.open.assert_called_once_with("/fake/path.pdf")

    async def test_analyze_no_fitz(self, analyzer):
        """Test that analysis works even when fitz is missing (graceful degradation)."""
        # Mock Gemini response
        self.mock_engine.generate.return_value = {
            "success": True,
            "response": '{"summary": "Test summary", "main_subject": "Math", "subject_area": "math", "key_concepts": [], "suggested_topics": [], "estimated_total_videos": 1}'
        }
        
        # Patch fitz to None to simulate missing PyMuPDF
        with patch("app.services.pipeline.content_analysis.pdf.fitz", None):
            result = await analyzer.analyze("any.pdf", "id")
            
            # Should still work but won't have page count info
            assert result["file_id"] == "id"
            assert result["material_type"] == "pdf"
            assert result["total_content_pages"] == 0  # No page count without fitz
            assert result["summary"] == "Test summary"

    def test_representative_sample(self, analyzer):
        """Test sampling logic in BaseAnalyzer."""
        long_text = "A" * 20000
        sample = analyzer._get_representative_sample(long_text, max_chars=100)
        
        assert len(sample) <= 200 # combined with markers
        assert "[...content continues...]" in sample
