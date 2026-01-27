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

        from app.services.prompting_engine import format_prompt
        prompt = format_prompt("ANALYZE_IMAGE")

        # Create image part for Gemini
        # Vertex AI uses from_data(), Gemini API uses from_bytes()
        try:
            image_part = self.types.Part.from_data(data=image_data, mime_type=mime_type)
        except AttributeError:
            # Fallback for Gemini API
            image_part = self.types.Part.from_bytes(data=image_data, mime_type=mime_type)

        # Define response schema for structured JSON output
        response_schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "main_subject": {"type": "string"},
                "subject_area": {"type": "string", "enum": ["math", "cs", "physics", "economics", "biology", "engineering", "general"]},
                "key_concepts": {"type": "array", "items": {"type": "string"}},
                "detected_math_elements": {"type": "integer"},
                "extracted_content": {"type": "array", "items": {"type": "string"}},
                "suggested_topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "estimated_duration": {"type": "integer"},
                            "complexity": {"type": "string"},
                            "subject_area": {"type": "string"},
                            "subtopics": {"type": "array", "items": {"type": "string"}},
                            "prerequisites": {"type": "array", "items": {"type": "string"}},
                            "visual_ideas": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["index", "title", "description", "estimated_duration", "complexity"]
                    }
                },
                "estimated_total_videos": {"type": "integer"}
            },
            "required": ["summary", "main_subject", "subject_area", "key_concepts", "suggested_topics", "estimated_total_videos"]
        }

        from app.services.prompting_engine import PromptConfig
        config = PromptConfig(
            temperature=0.7,
            max_output_tokens=4096,
            timeout=90,
            response_format="json"
        )

        result = await self.engine.generate(
            prompt=prompt,
            config=config,
            response_schema=response_schema,
            contents=[prompt, image_part]
        )

        response_text = result.get("response", "") if result.get("success") else ""
        return self._parse_json_response(response_text)
