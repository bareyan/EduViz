"""
Material Analyzer - Main entry point for document analysis

Dispatches to appropriate analyzer (PDF, Image, or Text) based on file type.
This module coordinates analysis and maintains SRP by delegating type-specific
logic to specialized analyzer classes.
"""

import os
from typing import Dict, Any, Optional
from .pdf import PDFAnalyzer
from .image import ImageAnalyzer
from .text import TextAnalyzer


class MaterialAnalyzer:
    """Main analyzer that coordinates document analysis
    
    Delegates to specialized analyzers based on file type:
    - PDF files → PDFAnalyzer
    - Images (PNG, JPG, WebP, GIF) → ImageAnalyzer
    - Text files (.txt, .tex) → TextAnalyzer
    """

    def __init__(self, pipeline_name: Optional[str] = None):
        # Initialize specialized analyzers with pipeline override
        self.pdf_analyzer = PDFAnalyzer(pipeline_name=pipeline_name)
        self.image_analyzer = ImageAnalyzer(pipeline_name=pipeline_name)
        self.text_analyzer = TextAnalyzer(pipeline_name=pipeline_name)

    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """
        Main analysis entry point
        
        Routes to appropriate analyzer based on file extension.
        
        Args:
            file_path: Path to the file to analyze
            file_id: Unique identifier for the file
            
        Returns:
            Analysis results including topics, summary, and metadata
            
        Raises:
            ValueError: If file type is not supported
        """
        file_ext = os.path.splitext(file_path)[1].lower()

        if file_ext == ".pdf":
            return await self.pdf_analyzer.analyze(file_path, file_id)
        elif file_ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            return await self.image_analyzer.analyze(file_path, file_id)
        elif file_ext in [".tex", ".txt"]:
            return await self.text_analyzer.analyze(file_path, file_id)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
