"""
Analysis module - Educational content analysis with Gemini AI

This module provides analysis of educational materials (PDFs, images, text files)
to extract structure, identify topics, and suggest comprehensive video content.

Architecture:
- MaterialAnalyzer: Main entry point (coordinator pattern)
- PDFAnalyzer: Specialized PDF analysis
- ImageAnalyzer: Specialized image analysis (with vision)
- TextAnalyzer: Specialized text file analysis
- BaseAnalyzer: Shared functionality and Gemini integration

Each analyzer respects Single Responsibility Principle:
- Handles one file type
- Delegates to Gemini for content analysis
- Returns structured topic suggestions

Usage:
    from app.services.analysis import MaterialAnalyzer
    
    analyzer = MaterialAnalyzer()
    result = await analyzer.analyze("path/to/file.pdf", "file_id_123")
"""

from .analyzer import MaterialAnalyzer
from .pdf import PDFAnalyzer
from .image import ImageAnalyzer
from .text import TextAnalyzer
from .base import BaseAnalyzer

__all__ = [
    "MaterialAnalyzer",
    "PDFAnalyzer",
    "ImageAnalyzer",
    "TextAnalyzer",
    "BaseAnalyzer",
]
