"""
DEPRECATED: Import compatibility shim

This module has been refactored into the 'analysis' package for better organization.
Existing imports will continue to work via this shim.

New code should import directly from the analysis package:
    from app.services.analysis import MaterialAnalyzer

This file will be removed in a future version.
"""

# Forward imports from new modular structure
from app.services.analysis import (
    MaterialAnalyzer,
    PDFAnalyzer,
    ImageAnalyzer,
    TextAnalyzer,
    BaseAnalyzer,
)

__all__ = [
    "MaterialAnalyzer",
    "PDFAnalyzer",
    "ImageAnalyzer",
    "TextAnalyzer",
    "BaseAnalyzer",
]
