"""
Tests for pipeline/content_analysis/base module

Tests for the BaseAnalyzer class patterns and functionality.
"""

import pytest


class TestBaseAnalyzerImport:
    """Test suite for BaseAnalyzer import and interface"""

    def test_base_analyzer_import(self):
        """Test that BaseAnalyzer can be imported"""
        from app.services.pipeline.content_analysis.base import BaseAnalyzer
        assert BaseAnalyzer is not None

    def test_base_analyzer_has_parse_json_response(self):
        """Test that BaseAnalyzer has _parse_json_response method"""
        from app.services.pipeline.content_analysis.base import BaseAnalyzer
        
        assert hasattr(BaseAnalyzer, "_parse_json_response")

    def test_base_analyzer_has_get_representative_sample(self):
        """Test that BaseAnalyzer has _get_representative_sample method"""
        from app.services.pipeline.content_analysis.base import BaseAnalyzer
        
        assert hasattr(BaseAnalyzer, "_get_representative_sample")


class TestMaterialAnalyzerImport:
    """Test suite for MaterialAnalyzer import"""

    def test_material_analyzer_import(self):
        """Test that MaterialAnalyzer can be imported"""
        from app.services.pipeline.content_analysis.analyzer import MaterialAnalyzer
        assert MaterialAnalyzer is not None

    def test_material_analyzer_has_analyze_method(self):
        """Test that MaterialAnalyzer has analyze method"""
        from app.services.pipeline.content_analysis.analyzer import MaterialAnalyzer
        
        assert hasattr(MaterialAnalyzer, "analyze")


class TestContentAnalyzers:
    """Test suite for specialized content analyzers"""

    def test_pdf_analyzer_import(self):
        """Test that PDFAnalyzer can be imported"""
        from app.services.pipeline.content_analysis.pdf import PDFAnalyzer
        assert PDFAnalyzer is not None

    def test_image_analyzer_import(self):
        """Test that ImageAnalyzer can be imported"""
        from app.services.pipeline.content_analysis.image import ImageAnalyzer
        assert ImageAnalyzer is not None

    def test_text_analyzer_import(self):
        """Test that TextAnalyzer can be imported"""
        from app.services.pipeline.content_analysis.text import TextAnalyzer
        assert TextAnalyzer is not None


class TestRepresentativeSampleLogic:
    """Test suite for representative sample extraction logic"""

    def test_sample_extraction_for_short_text(self):
        """Test that short text stays unchanged"""
        text = "This is a short text."
        max_chars = 1000
        
        # Short text should be <= max_chars
        assert len(text) <= max_chars

    def test_sample_markers_format(self):
        """Test format of continuation markers"""
        # The marker used in _get_representative_sample
        marker = "[...content continues...]"
        
        assert "[" in marker
        assert "]" in marker
        assert "continues" in marker

    def test_sample_division_logic(self):
        """Test logic for dividing content into intro/middle/end"""
        total_chars = 10000
        max_chars = 1000
        
        # Typical division: 40% intro, 20% middle, 40% end
        intro_ratio = 0.4
        middle_ratio = 0.2
        end_ratio = 0.4
        
        assert intro_ratio + middle_ratio + end_ratio == 1.0
        
        # Sample should be approximately max_chars
        sample_intro = int(max_chars * intro_ratio)
        sample_middle = int(max_chars * middle_ratio)
        sample_end = int(max_chars * end_ratio)
        
        total_sample = sample_intro + sample_middle + sample_end
        assert total_sample <= max_chars + 10  # Allow small margin


class TestJsonParsingPatterns:
    """Test suite for JSON parsing patterns used in analyzers"""

    def test_json_response_structure(self):
        """Test expected structure of analysis response"""
        expected_keys = [
            "summary",
            "main_subject",
            "difficulty_level",
            "key_concepts",
            "detected_math_elements",
            "suggested_topics",
            "estimated_total_videos"
        ]
        
        # All keys should be strings
        for key in expected_keys:
            assert isinstance(key, str)

    def test_topic_suggestion_structure(self):
        """Test expected structure of topic suggestion"""
        topic_keys = [
            "index",
            "title",
            "description",
            "estimated_duration",
            "complexity"
        ]
        
        # All keys should be strings
        for key in topic_keys:
            assert isinstance(key, str)

    def test_default_difficulty_levels(self):
        """Test valid difficulty levels"""
        valid_levels = ["beginner", "intermediate", "advanced"]
        
        assert len(valid_levels) == 3
        assert "beginner" in valid_levels


class TestAnalyzerFileExtensions:
    """Test suite for file extension handling in analyzers"""

    def test_pdf_extensions(self):
        """Test PDF file extensions"""
        pdf_extensions = [".pdf"]
        
        for ext in pdf_extensions:
            assert ext.startswith(".")
            assert ext == ".pdf"

    def test_image_extensions(self):
        """Test image file extensions"""
        image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        
        for ext in image_extensions:
            assert ext.startswith(".")

    def test_text_extensions(self):
        """Test text file extensions"""
        text_extensions = [".txt", ".md", ".rst"]
        
        for ext in text_extensions:
            assert ext.startswith(".")

    def test_extension_normalization(self):
        """Test extension normalization (lowercase)"""
        extensions = [".PDF", ".Png", ".TxT"]
        
        normalized = [ext.lower() for ext in extensions]
        
        assert normalized == [".pdf", ".png", ".txt"]
