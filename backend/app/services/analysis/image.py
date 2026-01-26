"""
Image analysis using Gemini Vision

Handles analysis of PNG, JPG, WebP, GIF images for educational content.
"""

import asyncio
from pathlib import Path
from typing import Dict, Any
from .base import BaseAnalyzer


class ImageAnalyzer(BaseAnalyzer):
    """Analyzes images using Gemini Vision API"""

    # MIME type mapping
    MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }

    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze an image using Gemini Vision"""
        # Read and encode image
        with open(file_path, "rb") as f:
            image_data = f.read()

        # Use Gemini to analyze with vision
        analysis = await self._gemini_analyze_image(image_data, file_path)

        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "image",
            "total_content_pages": 1,
            **analysis
        }

    async def _gemini_analyze_image(self, image_data: bytes, file_path: str) -> Dict[str, Any]:
        """Use Gemini Vision to analyze an image"""
        # Determine mime type
        ext = Path(file_path).suffix.lower()
        mime_type = self.MIME_TYPES.get(ext, "image/png")

        prompt = """You are an expert educator preparing COMPREHENSIVE educational video content.

Analyze this content from the image. Extract all text, equations, diagrams, concepts, code, or information visible.
IMPORTANT: Detect the SUBJECT AREA (math, computer science, physics, economics, biology, engineering, general).

Create ONE comprehensive video that covers ALL the content in this image:
- The video should REPLACE reading/studying this image entirely
- Include all concepts, explanations, and examples visible
- Show step-by-step explanations visually

Respond with ONLY valid JSON (no markdown, no code blocks):
{
    "summary": "Comprehensive summary of ALL content in this image",
    "main_subject": "The primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all", "concepts", "visible", "in", "image"],
    "detected_math_elements": 5,
    "extracted_content": ["key content items"],
    "suggested_topics": [
        {
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive video covering EVERYTHING in this image.",
            "estimated_duration": 20,
            "complexity": "comprehensive",
            "subject_area": "math|cs|physics|economics|biology|engineering|general",
            "subtopics": ["every", "concept", "visible"],
            "prerequisites": ["required background"],
            "visual_ideas": ["step-by-step explanations", "visualizations"]
        }
    ],
    "estimated_total_videos": 1
}

CRITICAL: Create exactly ONE comprehensive video covering everything."""

        # Create image part for Gemini
        # Vertex AI uses from_data(), Gemini API uses from_bytes()
        try:
            image_part = self.types.Part.from_data(data=image_data, mime_type=mime_type)
        except AttributeError:
            # Fallback for Gemini API
            image_part = self.types.Part.from_bytes(data=image_data, mime_type=mime_type)

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=[prompt, image_part]
        )

        return self._parse_json_response(response.text)
